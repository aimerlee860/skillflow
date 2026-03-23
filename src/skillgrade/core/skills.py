"""Skill detection module."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def detect_skills(skill_dir: Path) -> list[dict[str, Any]]:
    """Detect skills in the given directory.

    Searches in order:
    1. skill_dir/SKILL.md (root directory is a skill)
    2. skill_dir/skills/{name}/SKILL.md
    3. skill_dir/.agents/skills/{name}/SKILL.md
    4. skill_dir/.claude/skills/{name}/SKILL.md
    """
    skills = []

    if (skill_dir / "SKILL.md").exists():
        skill = _parse_skill_file(skill_dir / "SKILL.md", skill_dir.name)
        if skill:
            skill["path"] = str(skill_dir / "SKILL.md")
            skills.append(skill)

    search_paths = [
        skill_dir / "skills",
        skill_dir / ".agents" / "skills",
        skill_dir / ".claude" / "skills",
    ]

    for search_path in search_paths:
        if not search_path.exists():
            continue

        for skill_path in search_path.iterdir():
            if not skill_path.is_dir():
                continue
            skill_file = skill_path / "SKILL.md"
            if skill_file.exists():
                skill = _parse_skill_file(skill_file, skill_path.name)
                if skill:
                    skill["path"] = str(skill_file)
                    skills.append(skill)

    return skills


def _parse_skill_file(skill_file: Path, default_name: str) -> dict[str, Any] | None:
    """Parse a SKILL.md file and extract metadata."""
    content = skill_file.read_text()

    name = default_name
    description = ""

    if content.startswith("---"):
        match = re.match(r"^---\n(.*?)---", content, re.DOTALL)
        if match:
            frontmatter = match.group(1)
            for line in frontmatter.split("\n"):
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("description:"):
                    description = line.split(":", 1)[1].strip()

            content = content[match.end() :]

    if not description:
        first_heading = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if first_heading:
            description = first_heading.group(1)

    return {
        "name": name.lower().replace(" ", "-"),
        "description": description,
        "path": str(skill_file),
    }


def get_skill_dir(skill_dir: Path) -> Path | None:
    """Get the actual skill directory containing SKILL.md."""
    if (skill_dir / "SKILL.md").exists():
        return skill_dir

    for subdir in ["skills", ".agents/skills", ".claude/skills"]:
        skill_path = skill_dir / subdir
        if skill_path.exists():
            for item in skill_path.iterdir():
                if item.is_dir() and (item / "SKILL.md").exists():
                    return item

    return None
