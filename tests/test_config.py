"""Tests for config module."""

import pytest
from pathlib import Path
from skillgrade.core.config import (
    load_eval_config,
    parse_eval_config,
    generate_template,
    resolve_file_or_inline,
)


def test_parse_eval_config():
    """Test parsing a basic eval configuration."""
    raw = {
        "version": "1",
        "defaults": {"agent": "openai", "trials": 3},
        "tasks": [
            {
                "name": "test-task",
                "instruction": "Do something",
                "graders": [{"type": "deterministic", "run": "echo test", "weight": 1.0}],
            }
        ],
    }

    config = parse_eval_config(raw, Path("."))
    assert config.version == "1"
    assert len(config.tasks) == 1
    assert config.tasks[0].name == "test-task"
    assert config.tasks[0].trials == 3


def test_generate_template():
    """Test template generation."""
    template = generate_template([])
    assert 'version: "1"' in template
    assert "tasks:" in template
    assert "agent: openai" in template


def test_resolve_file_or_inline():
    """Test file path resolution."""
    content = resolve_file_or_inline("simple content", Path("."))
    assert content == "simple content"

    content = resolve_file_or_inline("line1\nline2", Path("."))
    assert content == "line1\nline2"
