"""Template-based skill generation - converts Jinja2 templates to skill references.

This module provides a bridge between the old template system and the new
skill-creator based approach. Templates can be used as quick-start references
when creating new skills.
"""

from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape


# Template skill definitions - these serve as references for common skill types
TEMPLATE_SKILLS = {
    "default": {
        "name": "default",
        "description": "A general-purpose skill template with basic structure.",
        "guidance": """
Use this template when creating a general-purpose skill. Key elements:

1. **Clear Instructions**: State what the agent should do in imperative form
2. **Step-by-Step Process**: Break down complex tasks into numbered steps
3. **Examples**: Provide 2-3 concrete examples of input/output
4. **Constraints**: List important limitations and requirements
5. **Output Format**: Specify the expected output structure
""",
    },
    "code-review": {
        "name": "code-review",
        "description": "Review code for correctness, readability, performance, security, and best practices.",
        "guidance": """
Use this template for code review skills. Key elements:

1. **Review Checklist**: Define specific criteria to check
   - Correctness: Does the code work as intended?
   - Readability: Is the code easy to understand?
   - Performance: Are there obvious performance issues?
   - Security: Are there potential vulnerabilities?
   - Best Practices: Does it follow language idioms?

2. **Structured Output**: Use a consistent format for review results
   ```
   ## Summary
   ## Issues Found (with severity)
   ## Suggestions
   ## Verdict (APPROVED/NEEDS_CHANGES/REJECTED)
   ```

3. **Severity Levels**: Critical, High, Medium, Low
""",
    },
    "documentation": {
        "name": "documentation",
        "description": "Generate clear, complete documentation with examples and consistent style.",
        "guidance": """
Use this template for documentation skills. Key elements:

1. **Documentation Guidelines**:
   - Clarity: Use simple, direct language
   - Completeness: Cover all parameters, return values, edge cases
   - Examples: Include practical usage examples
   - Consistency: Follow the project's documentation style

2. **Common Formats**:
   - Markdown for README and docs
   - Docstrings for code
   - JSDoc/similar for typed documentation

3. **Structure**:
   - Overview/Summary
   - Parameters/Arguments
   - Return Values
   - Examples
   - Notes/Caveats
""",
    },
    "testing": {
        "name": "testing",
        "description": "Create comprehensive tests with good coverage, isolation, and clear structure.",
        "guidance": """
Use this template for testing skills. Key elements:

1. **Testing Guidelines**:
   - Coverage: Test happy paths, edge cases, error conditions
   - Isolation: Each test should be independent
   - Clarity: Test names should describe what is being tested
   - Assertions: Use meaningful assertion messages

2. **Test Structure (AAA Pattern)**:
   ```python
   def test_<scenario>_<expected_result>():
       # Arrange
       ...

       # Act
       ...

       # Assert
       ...
   ```

3. **Test Categories**:
   - Unit tests
   - Integration tests
   - End-to-end tests
   - Performance tests
""",
    },
}


class TemplateSkillLoader:
    """Loads and renders skill templates, serving as references for skill creation."""

    def __init__(self, template_dir: Optional[Path] = None):
        """Initialize the template loader.

        Args:
            template_dir: Directory containing Jinja2 templates
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(default=False),
        )

    def get_template_guidance(self, template_name: str) -> str:
        """Get the guidance text for a template.

        Args:
            template_name: Name of the template (default, code-review, etc.)

        Returns:
            Guidance text for using this template
        """
        template_skill = TEMPLATE_SKILLS.get(template_name, TEMPLATE_SKILLS["default"])
        return template_skill["guidance"]

    def render_skill_md(
        self,
        name: str,
        description: str,
        template: str = "default",
        examples: Optional[list[str]] = None,
        constraints: Optional[list[str]] = None,
    ) -> str:
        """Render a SKILL.md file from a template.

        Args:
            name: Skill name
            description: Skill description
            template: Template to use
            examples: List of examples
            constraints: List of constraints

        Returns:
            Rendered SKILL.md content
        """
        try:
            tmpl = self.env.get_template(f"{template}/SKILL.md.j2")
        except Exception:
            tmpl = self.env.get_template("default/SKILL.md.j2")

        return tmpl.render(
            name=name,
            description=description,
            examples=examples or [],
            constraints=constraints or [],
        )

    def render_eval_yaml(self, name: str, description: str) -> str:
        """Render an eval.yaml file.

        Args:
            name: Skill name
            description: Skill description

        Returns:
            Rendered eval.yaml content
        """
        tmpl = self.env.get_template("default/eval.yaml.j2")
        return tmpl.render(name=name, description=description)

    def list_templates(self) -> list[dict[str, str]]:
        """List all available templates with their descriptions.

        Returns:
            List of template info dicts
        """
        return [
            {
                "name": info["name"],
                "description": info["description"],
            }
            for info in TEMPLATE_SKILLS.values()
        ]

    def get_template_as_reference(self, template_name: str) -> str:
        """Get a template formatted as a reference document.

        This is useful for injecting template guidance into the
        skill-creator's context when creating similar skills.

        Args:
            template_name: Name of the template

        Returns:
            Markdown-formatted reference document
        """
        template_skill = TEMPLATE_SKILLS.get(template_name, TEMPLATE_SKILLS["default"])

        # Also load the actual template file if it exists
        template_content = ""
        try:
            template_path = self.template_dir / template_name / "SKILL.md.j2"
            if template_path.exists():
                template_content = template_path.read_text()
        except Exception:
            pass

        return f"""# {template_name} Template Reference

## Description
{template_skill['description']}

## Guidance
{template_skill['guidance']}
{f'''
## Template Structure
```markdown
{template_content}
```
''' if template_content else ''}
"""


def create_skill_from_template(
    skill_dir: Path,
    name: str,
    description: str,
    template: str = "default",
    examples: Optional[list[str]] = None,
    constraints: Optional[list[str]] = None,
) -> Path:
    """Create a skill from a template (quick-start mode).

    This is a convenience function for quickly creating skills without
    the full LLM-powered creation process. Use this for simple skills
    or as a starting point.

    Args:
        skill_dir: Parent directory for the skill
        name: Skill name
        description: Skill description
        template: Template to use
        examples: List of examples
        constraints: List of constraints

    Returns:
        Path to the created skill directory
    """
    loader = TemplateSkillLoader()

    skill_path = skill_dir / name
    skill_path.mkdir(parents=True, exist_ok=True)

    # Generate SKILL.md
    skill_content = loader.render_skill_md(
        name=name,
        description=description,
        template=template,
        examples=examples or [],
        constraints=constraints or [],
    )
    (skill_path / "SKILL.md").write_text(skill_content)

    # Generate eval.yaml
    eval_content = loader.render_eval_yaml(name=name, description=description)
    (skill_path / "eval.yaml").write_text(eval_content)

    return skill_path
