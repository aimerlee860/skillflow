"""Skill context extractor - extracts concise context for LLM evaluation.

Extracts a compact representation of SKILL.md for use in LLM prompts:
1. YAML frontmatter (name, description, compatibility)
2. Markdown heading outline (all levels)
3. Important sections content (validation rules, required fields)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SkillContext:
    """Compact skill context for LLM evaluation.

    This is a condensed representation of SKILL.md that includes:
    - Basic metadata from frontmatter
    - Heading structure outline
    - Key sections content (validation rules, etc.)
    """

    # YAML frontmatter
    name: str
    description: str
    compatibility: list[str] = field(default_factory=list)

    # Markdown heading outline
    outline: list[str] = field(default_factory=list)

    # Raw summary for LLM (limited length)
    raw_summary: str = ""

    def to_prompt_text(self) -> str:
        """Convert to LLM prompt format.

        Returns a compact text representation suitable for LLM context.
        """
        parts = [
            f"技能名称: {self.name}",
            f"技能描述: {self.description}",
        ]

        if self.compatibility:
            parts.append(f"兼容性: {', '.join(self.compatibility)}")

        if self.outline:
            parts.append("\n技能结构大纲:")
            parts.extend(f"  {title}" for title in self.outline)

        return "\n".join(parts)

    def to_full_context(self) -> str:
        """Return full context including raw summary.

        Use this for more detailed LLM prompts.
        """
        base = self.to_prompt_text()
        if self.raw_summary:
            return f"{base}\n\n## 详细信息\n{self.raw_summary}"
        return base

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "compatibility": self.compatibility,
            "outline": self.outline,
            "rawSummary": self.raw_summary,
        }


class SkillContextExtractor:
    """Extracts compact skill context from SKILL.md.

    The extractor creates a condensed representation that:
    1. Preserves essential metadata
    2. Captures structural outline
    3. Includes important sections for difficulty assessment
    """

    # Sections that are important for difficulty assessment
    IMPORTANT_SECTIONS = [
        "验证规则", "validation", "必填", "required",
        "核心功能", "core function", "主要功能", "main function",
        "工作流程", "workflow", "处理流程", "process",
        "输入", "input", "输出", "output",
    ]

    def __init__(self, max_length: int = 2000):
        """Initialize the extractor.

        Args:
            max_length: Maximum length for raw summary text
        """
        self.max_length = max_length

    def extract(self, skill_md_path: Path) -> SkillContext:
        """Extract skill context from SKILL.md.

        Args:
            skill_md_path: Path to SKILL.md file

        Returns:
            SkillContext with condensed skill information
        """
        if not skill_md_path.exists():
            return SkillContext(name="unknown", description="")

        content = skill_md_path.read_text(encoding="utf-8")

        # 1. Extract YAML frontmatter
        frontmatter = self._extract_frontmatter(content)

        # 2. Extract heading outline
        outline = self._extract_outline(content)

        # 3. Build raw summary (frontmatter + outline + important sections)
        raw_summary = self._build_raw_summary(content, outline)

        return SkillContext(
            name=frontmatter.get("name", "unknown"),
            description=frontmatter.get("description", ""),
            compatibility=frontmatter.get("compatibility", []),
            outline=outline,
            raw_summary=raw_summary,
        )

    def _extract_frontmatter(self, content: str) -> dict[str, Any]:
        """Extract YAML frontmatter from content."""
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if match:
            try:
                return yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError:
                pass
        return {}

    def _extract_outline(self, content: str) -> list[str]:
        """Extract markdown heading outline (all levels).

        Returns list of indented headings representing the document structure.
        """
        # Remove frontmatter
        body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, flags=re.DOTALL)

        outline = []
        for line in body.split('\n'):
            # Match ##, ###, #### headings
            match = re.match(r'^(#{2,4})\s+(.+?)\s*$', line)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()
                # Indent based on level (## = no indent, ### = 2 spaces, #### = 4 spaces)
                indent = "  " * (level - 2)
                outline.append(f"{indent}{title}")

        return outline

    def _build_raw_summary(self, content: str, outline: list[str]) -> str:
        """Build raw summary text for LLM.

        Includes:
        1. Frontmatter
        2. Heading outline
        3. Important sections content
        """
        parts = []

        # 1. Frontmatter
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if frontmatter_match:
            parts.append("---")
            parts.append(frontmatter_match.group(1).strip())
            parts.append("---")

        # 2. Heading outline
        if outline:
            parts.append("\n# 技能结构")
            parts.extend(outline)

        # 3. Important sections content
        current_length = sum(len(p) for p in parts)

        for section_keyword in self.IMPORTANT_SECTIONS:
            if current_length >= self.max_length:
                break

            # Find section content (heading to next heading or end)
            pattern = rf'(#+\s*{section_keyword}.*?)(?=\n#+|\Z)'
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                section_content = match.group(1)[:500]  # Max 500 chars per section
                if current_length + len(section_content) < self.max_length:
                    parts.append(f"\n{section_content}")
                    current_length += len(section_content)

        return "\n".join(parts)[:self.max_length]
