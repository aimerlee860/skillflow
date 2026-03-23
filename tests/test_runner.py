"""Tests for runner module."""

import pytest
from pathlib import Path
from skillgrade.core.runner import EvalRunner, get_default_output_dir


@pytest.mark.asyncio
async def test_runner_setup(tmp_path):
    """Test runner setup creates correct directory structure."""
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("# Test Skill\n\nTest content.")

    runner = EvalRunner(skill_dir=tmp_path)

    temp_dir, config_path = await runner.setup()

    assert temp_dir.exists()
    assert config_path.exists()
    assert (temp_dir / "SKILL.md").exists()
    assert config_path.name == "eval.yaml"

    assert runner.results_dir.exists()
    assert runner.output_dir.exists()

    runner.cleanup()


@pytest.mark.asyncio
async def test_runner_with_custom_config(tmp_path):
    """Test runner with custom config file."""
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("# Test Skill\n\nTest content.")

    config_file = tmp_path / "custom_eval.yaml"
    config_file.write_text("""
version: "1"
tasks:
  - name: custom-task
    instruction: Do something
    graders:
      - type: deterministic
        run: 'import json; print(json.dumps({"score": 1.0, "details": "ok"}))'
        weight: 1.0
""")

    runner = EvalRunner(skill_dir=tmp_path, config_path=config_file)

    temp_dir, config_path = await runner.setup()

    config_content = config_path.read_text()
    assert "custom-task" in config_content

    runner.cleanup()


def test_get_default_output_dir():
    """Test default output directory generation."""
    output_dir = get_default_output_dir("my-skill")
    assert "my-skill" in str(output_dir)
    assert "skillgrade" in str(output_dir)
