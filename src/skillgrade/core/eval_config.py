"""Eval configuration generator."""

from pathlib import Path
from typing import Any, Optional

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

    def generate(
        self,
        name: str,
        description: str,
        rule_files: Optional[list[str]] = None,
    ) -> str:
        """Generate eval.yaml content.

        Args:
            name: Skill name
            description: Skill description
            rule_files: Optional list of rule file contents for deterministic graders

        Returns:
            eval.yaml content as string
        """
        # Build graders section
        has_rules = rule_files and len(rule_files) > 0
        llm_weight = 0.8 if has_rules else 1.0

        # LLM rubric grader (always included) - use new 'llm' type
        graders = [self._build_llm_grader(llm_weight)]

        # Add deterministic graders from rule files
        if has_rules:
            rule_weight = round(0.2 / len(rule_files), 2)
            for rule_content in rule_files:
                graders.append(self._build_deterministic_grader(rule_content, rule_weight))

        tmpl = self.env.get_template("default/eval.yaml.j2")
        return tmpl.render(
            name=name,
            description=description,
            graders=graders,
        )

    def _build_llm_grader(self, weight: float) -> dict[str, Any]:
        """Build LLM rubric grader configuration (uses 'llm' type for new format)."""
        return {
            "type": "llm",  # 使用新的 llm 类型
            "weight": weight,
            "rubric": """# Evaluation Rubric
Evaluate the agent's performance on this task:

1. **Task Completion**: Did the agent achieve the stated goal?
2. **Correctness**: Is the solution correct and functional?
3. **Approach**: Did the agent use an appropriate methodology?
4. **Efficiency**: Was the solution efficient without unnecessary steps?
5. **Tool Usage**: Did the agent use tools effectively?

Score guidelines:
- 1.0: Perfect completion with good approach
- 0.7-0.9: Minor issues but overall successful
- 0.4-0.6: Partial completion or significant issues
- 0.0-0.3: Failed or wrong approach""",
        }

    def _build_deterministic_grader(self, rule_content: str, weight: float) -> dict[str, Any]:
        """Build deterministic grader from rule file content."""
        return {
            "type": "deterministic",
            "weight": weight,
            "run": rule_content,
        }

    def generate_to_file(
        self,
        name: str,
        description: str,
        output_path: Path,
        rule_files: Optional[list[str]] = None,
    ) -> Path:
        """Generate eval.yaml and write to file.

        Args:
            name: Skill name
            description: Skill description
            output_path: Path to write eval.yaml
            rule_files: Optional list of rule file contents

        Returns:
            Path to the generated file
        """
        content = self.generate(name=name, description=description, rule_files=rule_files)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        return output_path
