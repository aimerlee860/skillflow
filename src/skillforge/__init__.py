"""Skill Forge - Create and initialize AI agent skills."""

__version__ = "0.1.0"

from skillforge.creator import SkillCreator
from skillforge.agent_creator import SkillCreatorAgent, load_skill
from skillforge.template_skills import (
    TemplateSkillLoader,
    TEMPLATE_SKILLS,
    create_skill_from_template,
)

__all__ = [
    "SkillCreator",
    "SkillCreatorAgent",
    "load_skill",
    "TemplateSkillLoader",
    "TEMPLATE_SKILLS",
    "create_skill_from_template",
]
