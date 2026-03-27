"""Evaluator - runs skillgrade and parses results."""

import asyncio
import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from skillevol.core.types import EvalConfig, EvalResult


class Evaluator:
    def __init__(self, config: EvalConfig):
        self.config = config
        self._skillgrade_available = self._check_skillgrade()

    def _check_skillgrade(self) -> bool:
        result = shutil.which(self.config.skillgrade_cmd)
        return result is not None

    async def evaluate(self, skill_md_content: str) -> EvalResult:
        if not self._skillgrade_available:
            raise RuntimeError("skillgrade not found. Please install skillgrade or provide path.")

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)

            # Copy all files from original skill directory (except SKILL.md which we'll write)
            # This ensures references/, scripts/, and other dependencies are available
            if self.config.skill_path and self.config.skill_path.exists():
                for item in self.config.skill_path.iterdir():
                    if item.name == "SKILL.md":
                        continue  # We'll write the modified SKILL.md below
                    dest = workspace / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)

            # Write the (possibly modified) SKILL.md
            skill_file = workspace / "SKILL.md"
            skill_file.write_text(skill_md_content)

            has_eval_config = False
            if self.config.eval_config_path and self.config.eval_config_path.exists():
                shutil.copy(self.config.eval_config_path, workspace / "eval.yaml")
                has_eval_config = True

            start_time = time.time()
            try:
                result = await asyncio.wait_for(
                    self._run_skillgrade(workspace, skip_init=has_eval_config),
                    # Allow generous timeout: each task can have its own timeout,
                    # but we need an overall limit to prevent hanging indefinitely.
                    # Default: num_tasks * task_timeout * trials + buffer
                    # Since we don't know num_tasks upfront, use a reasonable max
                    timeout=self.config.timeout_seconds * 10 * self.config.trials + 60,
                )
            except asyncio.TimeoutError:
                return EvalResult(
                    pass_rate=0.0,
                    pass_at_k=0.0,
                    combined_score=0.0,
                    num_trials=self.config.trials,
                    num_successes=0,
                    duration_seconds=self.config.timeout_seconds,
                    raw_output="Evaluation timed out",
                )
            duration = time.time() - start_time

        return self._parse_output(result, duration)

    async def _run_skillgrade(self, workspace: Path, skip_init: bool = False) -> str:
        cmd = [
            self.config.skillgrade_cmd,
            "eval",
            str(workspace),
            "--trials",
            str(self.config.trials),
        ]

        # Only skip init if we have an existing eval.yaml
        if skip_init:
            cmd.append("--skip-init")

        # Add parallel flag if > 1
        if self.config.parallel > 1:
            cmd.extend(["--parallel", str(self.config.parallel)])

        cmd.append("--json")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            return f"ERROR: {stderr.decode()}\n{stdout.decode()}"

        return stdout.decode()

    def _parse_output(self, output: str, duration: float) -> EvalResult:
        """Parse evaluation output and extract all metrics."""
        try:
            data = json.loads(output)

            # TASK-level metrics
            pass_rate = float(data.get("pass_rate", 0.0))
            pass_at_k = float(data.get("pass_at_k", 0.0))
            pass_pow_k = float(data.get("pass_pow_k", 0.0))
            reward = float(data.get("reward", 0.0))

            # SKILL-level metrics
            access_rate = float(data.get("access_rate", 1.0))
            deep_usage_rate = float(
                data.get("deep_usage_rate", data.get("deepUsageAccuracy", data.get("deepUsageRate", 0.0)))
            )
            false_positive_rate = float(data.get("false_positive_rate", 0.0))
            effective_usage_rate = float(
                data.get("effective_usage_rate", data.get("effectiveUsageRate", 0.0))
            )
            quality_score = float(data.get("quality_score", 0.0))

            trials = data.get("trials", self.config.trials)
            successes = self._count_successes_from_json(data)
        except (json.JSONDecodeError, ValueError, KeyError):
            # Fallback to text parsing
            metrics = self._parse_text_output(output)
            pass_rate = metrics["pass_rate"]
            pass_at_k = metrics["pass_at_k"]
            pass_pow_k = metrics.get("pass_pow_k", 0.0)
            reward = metrics.get("reward", 0.0)
            access_rate = metrics.get("access_rate", 1.0)
            deep_usage_rate = metrics.get("deep_usage_rate", 0.0)
            false_positive_rate = metrics.get("false_positive_rate", 0.0)
            effective_usage_rate = metrics.get("effective_usage_rate", 0.0)
            quality_score = metrics.get("quality_score", 0.0)
            trials = metrics.get("trials", self.config.trials)
            successes = metrics.get("successes", 0)

        result = EvalResult(
            pass_rate=pass_rate,
            pass_at_k=pass_at_k,
            pass_pow_k=pass_pow_k,
            reward=reward,
            access_rate=access_rate,
            deep_usage_rate=deep_usage_rate,
            false_positive_rate=false_positive_rate,
            effective_usage_rate=effective_usage_rate,
            quality_score=quality_score,
            num_trials=trials,
            num_successes=successes,
            duration_seconds=duration,
            raw_output=output,
        )
        result.compute_combined_score()
        return result

    def _count_successes_from_json(self, data: dict) -> int:
        """Count successful trials from JSON output."""
        results = data.get("results", [])
        successes = 0

        for item in results:
            if isinstance(item, dict) and "trials" in item:
                successes += sum(
                    1 for trial in item.get("trials", []) if trial.get("reward", 0) >= self.config.threshold
                )
            elif isinstance(item, dict) and item.get("reward", 0) >= self.config.threshold:
                successes += 1

        return successes

    def _parse_text_output(self, output: str) -> dict:
        """Parse text output to extract metrics when JSON parsing fails."""
        metrics = {}

        # TASK metrics
        pass_rate_match = re.search(r"Pass rate:\s*([\d.]+)%", output)
        metrics["pass_rate"] = float(pass_rate_match.group(1)) / 100 if pass_rate_match else 0.0

        pass_at_k_match = re.search(r"Pass @\d+:\s*([\d.]+)%", output)
        metrics["pass_at_k"] = float(pass_at_k_match.group(1)) / 100 if pass_at_k_match else 0.0

        pass_pow_k_match = re.search(r"Pass POW @\d+:\s*([\d.]+)%", output)
        metrics["pass_pow_k"] = float(pass_pow_k_match.group(1)) / 100 if pass_pow_k_match else 0.0

        reward_match = re.search(r"Reward:\s*([\d.]+)", output)
        metrics["reward"] = float(reward_match.group(1)) if reward_match else 0.0

        # SKILL metrics (may not be present in all outputs)
        access_rate_match = re.search(r"Access rate:\s*([\d.]+)%", output)
        metrics["access_rate"] = float(access_rate_match.group(1)) / 100 if access_rate_match else 1.0

        deep_usage_match = re.search(r"Deep usage:\s*([\d.]+)%", output)
        metrics["deep_usage_rate"] = float(deep_usage_match.group(1)) / 100 if deep_usage_match else 0.0

        fp_rate_match = re.search(r"False positive:\s*([\d.]+)%", output)
        metrics["false_positive_rate"] = float(fp_rate_match.group(1)) / 100 if fp_rate_match else 0.0

        effective_match = re.search(r"Effective usage:\s*([\d.]+)%", output)
        metrics["effective_usage_rate"] = float(effective_match.group(1)) / 100 if effective_match else 0.0

        quality_match = re.search(r"Quality score:\s*([\d.]+)", output)
        metrics["quality_score"] = float(quality_match.group(1)) if quality_match else 0.0

        # Trial counts
        trial_matches = re.findall(r"trial \d+", output)
        metrics["trials"] = len(trial_matches) if trial_matches else self.config.trials

        success_matches = re.findall(r"✓|PASS", output)
        metrics["successes"] = len(success_matches)

        return metrics
