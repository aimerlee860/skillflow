"""Tests for skills module."""

import pytest
from pathlib import Path
from skillgrade.core.skills import detect_skills, get_skill_dir


def test_detect_skills_empty_dir(tmp_path):
    """Test detection in empty directory."""
    skills = detect_skills(tmp_path)
    assert skills == []


def test_detect_skills_with_skill_md(tmp_path):
    """Test detection when SKILL.md exists."""
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("# Test Skill\n\nThis is a test skill.")

    skills = detect_skills(tmp_path)
    assert len(skills) == 1
    assert "name" in skills[0]
    assert skills[0]["path"] == str(skill_file)


def test_get_skill_dir(tmp_path):
    """Test getting skill directory."""
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("# Test")

    result = get_skill_dir(tmp_path)
    assert result == tmp_path
