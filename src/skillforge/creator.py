"""Skill creator - generates SKILL.md and eval.yaml files."""

from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape


class SkillCreator:
    """Creates new skill projects with SKILL.md and eval.yaml."""

    def __init__(self, template_dir: Optional[Path] = None):
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        self.template_dir = template_dir
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
        """Create a new skill directory with SKILL.md and eval.yaml.

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

        # Generate eval.yaml
        eval_content = self._render_eval_yaml(name=name, description=description)
        (skill_path / "eval.yaml").write_text(eval_content)

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

    def _render_eval_yaml(self, name: str, description: str) -> str:
        """Render eval.yaml from template."""
        tmpl = self.env.get_template("default/eval.yaml.j2")
        return tmpl.render(name=name, description=description)

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
