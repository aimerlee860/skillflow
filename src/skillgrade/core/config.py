"""Core configuration module."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from ..types import (
    EvalConfig,
    EvalReport,
    GraderConfig,
    GraderType,
    TaskConfig,
    TrialResult,
    WorkspaceFile,
)


DEFAULT_CONFIG = {
    "trials": 5,
    "timeout": 300,
    "threshold": 0.8,
}


def _get_current_model_name() -> str:
    """Get the current LLM model name from environment or .env file."""
    import os
    from dotenv import load_dotenv
    from pathlib import Path

    # Load from .env if exists
    project_root = Path(__file__).resolve().parent.parent.parent
    load_dotenv(project_root / ".env")

    return os.environ.get("LLM_MODEL_NAME", "gpt-4o")


def load_eval_config(skill_dir: Path) -> EvalConfig:
    """Load and parse eval.yaml from skill directory."""
    config_path = skill_dir / "eval.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"eval.yaml not found in {skill_dir}")

    content = config_path.read_text()
    raw = yaml.safe_load(content)

    return parse_eval_config(raw, skill_dir)


def load_eval_config_from_path(config_path: Path, base_dir: Path | None = None) -> EvalConfig:
    """Load and parse eval.yaml from a specific path.

    Args:
        config_path: Path to the eval.yaml file
        base_dir: Base directory for resolving file references (defaults to config_path's parent)

    Returns:
        Parsed EvalConfig

    Raises:
        FileNotFoundError: If config file doesn't exist
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    if base_dir is None:
        base_dir = config_path.parent

    content = config_path.read_text()
    raw = yaml.safe_load(content)

    return parse_eval_config(raw, base_dir)


def save_eval_config(config: EvalConfig | dict[str, Any], output_path: Path) -> Path:
    """Save eval configuration to a YAML file.

    Args:
        config: EvalConfig object or raw dict
        output_path: Path to save the config

    Returns:
        Path to the saved file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if hasattr(config, "to_dict"):
        config = config.to_dict()

    # Remove unnecessary fields for saved config
    model_name = _get_current_model_name()
    if "defaults" in config:
        config["defaults"].pop("docker", None)
        config["defaults"].pop("environment", None)
        config["defaults"].pop("provider", None)
        config["defaults"]["agent"] = model_name
        config["defaults"]["grader_model"] = model_name

    # Update grader model in each task
    for task in config.get("tasks", []):
        for grader in task.get("graders", []):
            grader["model"] = model_name

    content = yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True)
    output_path.write_text(content)

    return output_path


def parse_eval_config(raw: dict[str, Any], base_dir: Path) -> EvalConfig:
    """Parse raw configuration dictionary into EvalConfig."""
    defaults = {**DEFAULT_CONFIG, **raw.get("defaults", {})}

    tasks = []
    for task_raw in raw.get("tasks", []):
        task = parse_task(task_raw, defaults, base_dir)
        tasks.append(task)

    return EvalConfig(
        version=raw.get("version", "1"),
        skill=raw.get("skill"),
        defaults=defaults,
        tasks=tasks,
    )


def parse_task(task_raw: dict[str, Any], defaults: dict[str, Any], base_dir: Path) -> TaskConfig:
    """Parse a single task configuration."""
    workspace = []
    for ws_raw in task_raw.get("workspace", []):
        ws = WorkspaceFile(
            src=str(base_dir / ws_raw["src"]),
            dest=ws_raw["dest"],
            chmod=ws_raw.get("chmod"),
        )
        workspace.append(ws)

    graders = []
    for grader_raw in task_raw.get("graders", []):
        grader = parse_grader(grader_raw, defaults, base_dir)
        graders.append(grader)

    return TaskConfig(
        name=task_raw["name"],
        instruction=resolve_file_or_inline(task_raw["instruction"], base_dir),
        workspace=workspace,
        graders=graders,
        trials=task_raw.get("trials", defaults.get("trials", 5)),
        timeout=task_raw.get("timeout", defaults.get("timeout", 300)),
        agent=task_raw.get("agent", defaults.get("agent")),
        provider=task_raw.get("provider", defaults.get("provider")),
    )


def parse_grader(
    grader_raw: dict[str, Any], defaults: dict[str, Any], base_dir: Path
) -> GraderConfig:
    """Parse a grader configuration."""
    grader_type = GraderType(grader_raw["type"])

    run_content = None
    if grader_raw.get("run"):
        run_content = resolve_file_or_inline(grader_raw["run"], base_dir)

    rubric_content = None
    if grader_raw.get("rubric"):
        rubric_content = resolve_file_or_inline(grader_raw["rubric"], base_dir)

    return GraderConfig(
        type=grader_type,
        run=run_content,
        rubric=rubric_content,
        weight=grader_raw.get("weight", 1.0),
        model=grader_raw.get("model", defaults.get("grader_model")),
        setup=grader_raw.get("setup"),
    )


def resolve_file_or_inline(value: str, base_dir: Path) -> str:
    """Resolve a value that may be a file path or inline content."""
    stripped = value.strip()

    if _looks_like_file_path(stripped) and (base_dir / stripped).exists():
        return (base_dir / stripped).read_text()

    return value


def _looks_like_file_path(value: str) -> bool:
    """Check if a value looks like a file path rather than content."""
    if "\n" in value:
        return False
    if value.startswith("#") or value.startswith("-"):
        return False
    if re.match(r"^[a-zA-Z0-9_\-./]+$", value):
        return True
    return False


def generate_template(skills: list[dict[str, Any]]) -> str:
    """Generate an eval.yaml template."""
    skill_info = ""
    if skills:
        skill_info = f"Detected skill: {skills[0]['name']}\n"

    template = f"""# Skillgrade Evaluation Configuration
# Generated template - customize for your skill
#
# {skill_info}
# Documentation: https://github.com/mgechev/skillgrade#readme

version: "1"

defaults:
  agent: openai          # openai | claude (only openai supported in Python version)
  provider: local        # local only
  trials: 5              # number of independent runs per task
  timeout: 300           # seconds before agent is killed
  threshold: 0.8         # minimum pass rate for --ci mode
  grader_model: gpt-4o   # default LLM grader model

tasks:
  - name: example-task
    instruction: |
      TODO: Describe what the agent should do.
      Be specific about expected outputs and files.

    workspace: []
      # - src: fixtures/test-file.js
      #   dest: test.js

    graders:
      - type: deterministic
        run: |
          # Python grader must output JSON to stdout:
          # {{"score": 0.0-1.0, "details": "...", "checks": [...]}}
          import json
          print(json.dumps({{
              "score": 0.0,
              "details": "TODO: implement grader",
              "checks": []
          }}))
        weight: 0.7

      - type: llm_rubric
        rubric: |
          # Evaluate the agent's approach:
          # - Did the agent follow the correct workflow?
          # - Did it use appropriate tools?
          # - Was it efficient?
        weight: 0.3
"""
    return template


def save_report(report: EvalReport, output_dir: Path) -> Path:
    """Save an evaluation report to JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    import orjson

    timestamp = report.timestamp.replace(":", "-").replace(".", "-")
    filename = f"{report.task_name}_{timestamp}.json"
    filepath = output_dir / filename

    with open(filepath, "wb") as f:
        f.write(orjson.dumps(report.to_dict(), option=orjson.OPT_INDENT_2))

    return filepath
