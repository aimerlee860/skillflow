"""Tests for skillforge module - skill creation with agent support."""

import sys
from pathlib import Path

# Add src to path for testing without installation
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import pytest
from unittest.mock import Mock, patch, AsyncMock

from skillforge import (
    SkillCreator,
    TemplateSkillLoader,
    TEMPLATE_SKILLS,
    create_skill_from_template,
    load_skill,
)


class TestTemplateSkillLoader:
    """Tests for TemplateSkillLoader."""

    def test_list_templates(self):
        """Test listing available templates."""
        loader = TemplateSkillLoader()
        templates = loader.list_templates()

        assert len(templates) == 4
        template_names = [t["name"] for t in templates]
        assert "default" in template_names
        assert "code-review" in template_names
        assert "documentation" in template_names
        assert "testing" in template_names

    def test_get_template_guidance(self):
        """Test getting template guidance."""
        loader = TemplateSkillLoader()
        guidance = loader.get_template_guidance("code-review")

        assert "review" in guidance.lower()
        assert "checklist" in guidance.lower()

    def test_render_skill_md_default(self, tmp_path):
        """Test rendering default SKILL.md."""
        loader = TemplateSkillLoader()
        content = loader.render_skill_md(
            name="test-skill",
            description="A test skill",
            template="default",
            examples=["Example 1"],
            constraints=["Must be fast"],
        )

        assert "# test-skill" in content
        assert "A test skill" in content
        assert "Example 1" in content
        assert "Must be fast" in content

    def test_render_skill_md_code_review(self, tmp_path):
        """Test rendering code-review SKILL.md."""
        loader = TemplateSkillLoader()
        content = loader.render_skill_md(
            name="code-reviewer",
            description="Review code for issues",
            template="code-review",
        )

        assert "# code-reviewer" in content
        assert "Review Checklist" in content
        assert "Correctness" in content
        assert "Security" in content

    def test_render_eval_yaml(self):
        """Test rendering eval.yaml."""
        loader = TemplateSkillLoader()
        content = loader.render_eval_yaml(
            name="test-skill",
            description="A test skill",
        )

        assert "version:" in content
        assert "test-skill" not in content  # name not used in current template
        assert "tasks:" in content


class TestCreateSkillFromTemplate:
    """Tests for create_skill_from_template function."""

    def test_create_skill_default(self, tmp_path):
        """Test creating a skill from default template."""
        skill_path = create_skill_from_template(
            skill_dir=tmp_path,
            name="my-skill",
            description="Does something useful",
            template="default",
        )

        assert skill_path.exists()
        assert (skill_path / "SKILL.md").exists()
        assert (skill_path / "eval.yaml").exists()

        skill_content = (skill_path / "SKILL.md").read_text()
        assert "my-skill" in skill_content
        assert "Does something useful" in skill_content


class TestSkillCreator:
    """Tests for the original SkillCreator (backward compatibility)."""

    def test_create_skill(self, tmp_path):
        """Test creating a skill with original creator."""
        creator = SkillCreator()
        skill_path = creator.create(
            skill_dir=tmp_path,
            name="legacy-skill",
            description="A legacy skill",
            template="default",
        )

        assert skill_path.exists()
        assert (skill_path / "SKILL.md").exists()


class TestLoadSkill:
    """Tests for load_skill function."""

    def test_load_skill_creator(self):
        """Test loading the skill-creator skill."""
        skill = load_skill("skill-creator")

        assert skill["name"] == "skill-creator"
        assert "create" in skill["description"].lower()
        assert len(skill["body"]) > 100
        assert "SKILL.md" in skill["path"]

    def test_load_nonexistent_skill(self):
        """Test loading a skill that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_skill("nonexistent-skill")


class TestTEMPLATE_SKILLS:
    """Tests for TEMPLATE_SKILLS constant."""

    def test_template_skills_structure(self):
        """Test that TEMPLATE_SKILLS has correct structure."""
        assert "default" in TEMPLATE_SKILLS
        assert "code-review" in TEMPLATE_SKILLS
        assert "documentation" in TEMPLATE_SKILLS
        assert "testing" in TEMPLATE_SKILLS

        for name, skill in TEMPLATE_SKILLS.items():
            assert "name" in skill
            assert "description" in skill
            assert "guidance" in skill
            assert skill["name"] == name
