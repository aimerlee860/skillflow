"""Skill creator - generates SKILL.md files."""

from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Localized template strings
I18N = {
    "zh": {
        "instructions": "你是一个专门从事{description}的AI代理。",
        "guidelines": [
            "理解请求 - 在继续之前明确用户的具体需求",
            "遵循最佳实践 - 应用领域适当的标准和模式",
            "验证输入 - 检查是否提供了所需信息",
            "仔细执行 - 逐步执行任务",
            "验证结果 - 确保输出符合预期",
        ],
        "examples_header": "示例",
        "input": "输入",
        "expected": "预期",
        "constraints_header": "约束条件",
        "output_format_header": "输出格式",
        "output_format": [
            "摘要 - 简要描述已完成的工作",
            "详情 - 采取的具体操作或产生的结果",
            "后续步骤 - 任何需要跟进的操作（如适用）",
        ],
        "use_when": "当用户需要帮助处理",
    },
    "en": {
        "instructions": "You are an AI agent specialized in {description}.",
        "guidelines": [
            "Understand the request - Clarify the user's specific needs before proceeding",
            "Follow best practices - Apply domain-appropriate standards and patterns",
            "Validate inputs - Check that required information is provided",
            "Execute carefully - Perform the task step by step",
            "Verify results - Ensure the output meets expectations",
        ],
        "examples_header": "Examples",
        "input": "Input",
        "expected": "Expected",
        "constraints_header": "Constraints",
        "output_format_header": "Output Format",
        "output_format": [
            "Summary - Brief description of what was done",
            "Details - Specific actions taken or results produced",
            "Next Steps - Any follow-up actions needed (if applicable)",
        ],
        "use_when": "Use when users need help with",
    },
}


class SkillCreator:
    """Creates new skill projects with SKILL.md."""

    def __init__(self, template_dir: Optional[Path] = None, lang: str = "en"):
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        self.template_dir = template_dir
        self.lang = lang
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(default=False),
        )

    def create(
        self,
        skill_dir: Path,
        name: str,
        description: str,
        template: str = "default",
        examples: Optional[list[str]] = None,
        constraints: Optional[list[str]] = None,
    ) -> Path:
        """Create a new skill directory with SKILL.md only.

        Args:
            skill_dir: Parent directory where the skill will be created
            name: Name of the skill
            description: Brief description of what the skill does
            template: Template to use (default, code-review, etc.)
            examples: List of example descriptions
            constraints: List of constraints/requirements

        Returns:
            Path to the created skill directory
        """
        skill_path = skill_dir / name
        skill_path.mkdir(parents=True, exist_ok=True)

        # Generate SKILL.md
        skill_content = self._render_skill_md(
            name=name,
            description=description,
            template=template,
            examples=examples or [],
            constraints=constraints or [],
        )
        (skill_path / "SKILL.md").write_text(skill_content)

        return skill_path

    def create_from_codebase(
        self,
        skill_dir: Path,
        name: str,
        codebase_path: Path,
        description: Optional[str] = None,
    ) -> Path:
        """Create a skill by analyzing an existing codebase.

        Args:
            skill_dir: Parent directory where the skill will be created
            name: Name of the skill
            codebase_path: Path to the codebase to analyze
            description: Optional description (will be inferred if not provided)

        Returns:
            Path to the created skill directory
        """
        # Analyze codebase structure
        analysis = self._analyze_codebase(codebase_path)

        if description is None:
            description = analysis.get("inferred_description", f"Skill for {name}")

        return self.create(
            skill_dir=skill_dir,
            name=name,
            description=description,
            examples=analysis.get("examples", []),
            constraints=analysis.get("constraints", []),
        )

    def _render_skill_md(
        self,
        name: str,
        description: str,
        template: str,
        examples: list[str],
        constraints: list[str],
    ) -> str:
        """Render SKILL.md from template."""
        try:
            tmpl = self.env.get_template(f"{template}/SKILL.md.j2")
        except Exception:
            tmpl = self.env.get_template("default/SKILL.md.j2")

        return tmpl.render(
            name=name,
            description=description,
            examples=examples,
            constraints=constraints,
        )

    def _analyze_codebase(self, codebase_path: Path) -> dict:
        """Analyze codebase to infer skill structure."""
        analysis = {
            "inferred_description": "",
            "examples": [],
            "constraints": [],
        }

        # Look for common patterns
        if (codebase_path / "README.md").exists():
            readme = (codebase_path / "README.md").read_text()
            # Extract first paragraph as description
            lines = readme.strip().split("\n")
            for line in lines:
                if line.strip() and not line.startswith("#"):
                    analysis["inferred_description"] = line.strip()
                    break

        # Look for existing test files as examples
        test_files = list(codebase_path.glob("**/test_*.py")) + list(
            codebase_path.glob("**/*_test.py")
        )
        for test_file in test_files[:3]:
            analysis["examples"].append(f"Follow pattern in {test_file.relative_to(codebase_path)}")

        return analysis

    @staticmethod
    def list_templates() -> list[str]:
        """List available skill templates."""
        return ["default", "code-review", "documentation", "testing"]
