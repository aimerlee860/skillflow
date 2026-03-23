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
            skill_file = workspace / "SKILL.md"
            skill_file.write_text(skill_md_content)

            if self.config.eval_config_path and self.config.eval_config_path.exists():
                shutil.copy(self.config.eval_config_path, workspace / "eval.yaml")

            start_time = time.time()
            try:
                result = await asyncio.wait_for(
                    self._run_skillgrade(workspace),
                    timeout=self.config.timeout_seconds + 30,
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

    async def _run_skillgrade(self, workspace: Path) -> str:
        cmd = [
            self.config.skillgrade_cmd,
            "eval",
            str(workspace),
            "--trials",
            str(self.config.trials),
            "--json",
        ]

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
        try:
            data = json.loads(output)
            pass_rate = float(data.get("pass_rate", 0.0))
            pass_at_k = float(data.get("pass_at_k", 0.0))
            trials = data.get("trials", self.config.trials)
            successes = sum(
                1 for t in data.get("results", []) if t.get("reward", 0) >= self.config.threshold
            )
        except (json.JSONDecodeError, ValueError, KeyError):
            pass_rate, pass_at_k, trials, successes = self._parse_text_output(output)

        combined_score = (pass_rate * (1 + pass_at_k)) / 2

        return EvalResult(
            pass_rate=pass_rate,
            pass_at_k=pass_at_k,
            combined_score=combined_score,
            num_trials=trials,
            num_successes=successes,
            duration_seconds=duration,
            raw_output=output,
        )

    def _parse_text_output(self, output: str) -> tuple[float, float, int, int]:
        pass_rate_match = re.search(r"Pass rate:\s*([\d.]+)%", output)
        pass_at_k_match = re.search(r"Pass @\d+:\s*([\d.]+)%", output)

        pass_rate = float(pass_rate_match.group(1)) / 100 if pass_rate_match else 0.0
        pass_at_k = float(pass_at_k_match.group(1)) / 100 if pass_at_k_match else 0.0

        trial_matches = re.findall(r"trial \d+", output)
        trials = len(trial_matches) if trial_matches else self.config.trials

        success_matches = re.findall(r"✓|PASS", output)
        successes = len(success_matches)

        return pass_rate, pass_at_k, trials, successes
