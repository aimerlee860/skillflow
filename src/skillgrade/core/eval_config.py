"""Eval configuration generator."""

from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape


class EvalConfigGenerator:
    """Generates eval.yaml configuration files."""

    def __init__(self, template_dir: Optional[Path] = None):
        if template_dir is None:
            template_dir = Path(__file__).parent.parent.parent / "skillforge" / "templates"
        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(default=False),
        )

    def generate(self, name: str, description: str) -> str:
        """Generate eval.yaml content.

        Args:
            name: Skill name
            description: Skill description

        Returns:
            eval.yaml content as string
        """
        tmpl = self.env.get_template("default/eval.yaml.j2")
        return tmpl.render(name=name, description=description)

    def generate_to_file(self, name: str, description: str, output_path: Path) -> Path:
        """Generate eval.yaml and write to file.

        Args:
            name: Skill name
            description: Skill description
            output_path: Path to write eval.yaml

        Returns:
            Path to the generated file
        """
        content = self.generate(name=name, description=description)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        return output_path
