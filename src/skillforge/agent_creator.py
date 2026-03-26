"""Skill Creator Agent - Uses skill-creator skill to generate new skills."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional

from deepagents import create_deep_agent
from langchain_core.messages import HumanMessage, SystemMessage

from skillgrade.llm.client import LLMClient
from skillgrade.tools import shell, read_file, write_file, glob_files


class SkillCreatorAgent:
    """Agent that uses the skill-creator skill to generate new skills.

    This agent loads the skill-creator skill as system context and uses
    ReAct pattern to interactively create high-quality skills.
    """

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        max_iterations: int = 50,
    ):
        """Initialize the Skill Creator Agent.

        Args:
            model_name: Override model name
            base_url: Override base URL for API
            api_key: Override API key
            max_iterations: Maximum number of agent iterations
        """
        self.llm_client = LLMClient(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
        )
        self.max_iterations = max_iterations
        self.model_name = self.llm_client.model_name

        # Load the skill-creator skill
        self._skill_creator_content = self._load_skill_creator()

        # Available tools for skill creation
        self.tools = [shell, read_file, write_file, glob_files]

        # Build system prompt from skill-creator
        self.system_prompt = self._build_system_prompt()

        # Create the deep agent with skill-creator context
        self.graph = create_deep_agent(
            model=self.llm_client.chat,
            tools=self.tools,
            system_prompt=self.system_prompt,
        )

    def _load_skill_creator(self) -> str:
        """Load the skill-creator SKILL.md content."""
        skill_path = Path(__file__).parent / "skills" / "skill-creator" / "SKILL.md"
        if skill_path.exists():
            return skill_path.read_text()
        raise FileNotFoundError(
            f"skill-creator skill not found at {skill_path}. "
            "Please ensure the skill is installed."
        )

    def _build_system_prompt(self) -> str:
        """Build system prompt from skill-creator skill content."""
        # Extract the body (after frontmatter)
        content = self._skill_creator_content
        if content.startswith("---"):
            match = re.match(r"^---\n.*?---\n", content, re.DOTALL)
            if match:
                content = content[match.end() :]

        return f"""You are a Skill Creator Agent. Your job is to help users create high-quality AI agent skills.

Follow these instructions from the skill-creator skill:

{content}

---
Remember:
1. Always create SKILL.md with proper YAML frontmatter (name, description)
2. The description is the PRIMARY triggering mechanism - include what the skill does AND when to use it
3. Keep SKILL.md under 500 lines; use references/ for detailed content
4. Follow the progressive disclosure pattern
5. Create test cases and iterate based on feedback
"""

    async def create_skill(
        self,
        name: str,
        description: str,
        output_dir: Path,
        context: Optional[str] = None,
        examples: Optional[list[str]] = None,
        template: str = "default",
    ) -> Path:
        """Create a new skill using the skill-creator guidance.

        Args:
            name: Name of the skill to create
            description: What the skill should do
            output_dir: Directory to create the skill in
            context: Additional context (code snippets, docs, etc.)
            examples: Example use cases for the skill
            template: Template variant to use (default, code-review, etc.)

        Returns:
            Path to the created skill directory
        """
        skill_path = output_dir / name

        # Build the prompt
        prompt_parts = [
            f"Create a new skill with the following details:",
            f"",
            f"**Name**: {name}",
            f"**Description**: {description}",
            f"**Output directory**: {skill_path}",
        ]

        if context:
            prompt_parts.extend([
                f"",
                f"**Additional Context**:",
                context,
            ])

        if examples:
            prompt_parts.extend([
                f"",
                f"**Example Use Cases**:",
            ])
            for i, example in enumerate(examples, 1):
                prompt_parts.append(f"{i}. {example}")

        if template != "default":
            prompt_parts.extend([
                f"",
                f"**Template**: Use the {template} template style",
            ])

        prompt_parts.extend([
            f"",
            f"**IMPORTANT - Language Requirement**:",
            f"Detect the language used in the description and examples above.",
            f"Write ALL content (SKILL.md, comments, documentation) in the SAME language as the input.",
            f"If the description is in Chinese, write everything in Chinese.",
            f"If the description is in English, write everything in English.",
            f"",
            f"Please follow the skill-creator process:",
            f"1. Understand the intent and ask clarifying questions if needed",
            f"2. Create the SKILL.md with proper YAML frontmatter (name, description fields)",
            f"3. Add any necessary bundled resources (scripts/, references/, assets/)",
            f"",
            f"Create the skill files in: {skill_path}",
        ])

        prompt = "\n".join(prompt_parts)
        prompt += "\n\n**IMPORTANT**: After creating ALL files (SKILL.md and any references/scripts), create an empty file named '_DONE' in the skill directory to signal completion. Do NOT respond before creating _DONE."

        # Run the agent with astream to monitor _DONE file
        import asyncio

        done_marker = skill_path / "_DONE"

        async def run_with_early_exit():
            config = {
                "configurable": {"thread_id": f"skill-creation-{name}"},
                "recursion_limit": self.max_iterations,
            }
            async for _ in self.graph.astream(
                {"messages": [HumanMessage(content=prompt)]},
                config=config,
                stream_mode="updates",
            ):
                # Exit as soon as _DONE marker appears
                if done_marker.exists():
                    break

        timeout_occurred = False
        try:
            await asyncio.wait_for(run_with_early_exit(), timeout=180)
        except asyncio.TimeoutError:
            timeout_occurred = True
            print(f"Warning: Skill creation timed out after 180 seconds")
        except Exception as e:
            print(f"Error during skill creation: {e}")
        finally:
            # Clean up the marker file
            if done_marker.exists():
                done_marker.unlink()

        # Verify the skill was actually created
        skill_md_path = skill_path / "SKILL.md"
        if not skill_md_path.exists():
            if timeout_occurred:
                raise RuntimeError(
                    f"Skill creation timed out and {skill_path / 'SKILL.md'} was not created. "
                    "The LLM agent may need more time or there might be an API issue."
                )
            else:
                raise RuntimeError(
                    f"Skill creation failed: {skill_md_path} was not created. "
                    "Please check your LLM API configuration (LLM_BASE_URL, LLM_API_KEY)."
                )

        return skill_path

    async def improve_skill(
        self,
        skill_path: Path,
        feedback: str,
        output_dir: Optional[Path] = None,
    ) -> Path:
        """Improve an existing skill based on feedback.

        Args:
            skill_path: Path to the existing skill
            feedback: User feedback on what to improve
            output_dir: Optional output directory (defaults to same path)

        Returns:
            Path to the improved skill
        """
        if output_dir is None:
            output_dir = skill_path.parent

        skill_file = skill_path / "SKILL.md"
        if not skill_file.exists():
            raise FileNotFoundError(f"Skill not found at {skill_path}")

        current_skill = skill_file.read_text()

        prompt = f"""Improve the following skill based on user feedback.

**Current Skill** (at {skill_path}):
```
{current_skill}
```

**User Feedback**:
{feedback}

**Task**:
1. Read the current skill
2. Understand the feedback and identify what needs to change
3. Update the SKILL.md with improvements
4. Ensure the description field properly captures when to trigger
5. Keep the skill under 500 lines; move details to references/ if needed

Save the improved skill to: {skill_path}
"""

        result = await self.graph.ainvoke(
            {"messages": [HumanMessage(content=prompt)]},
            config={
                "configurable": {"thread_id": f"skill-improve-{skill_path.name}"},
                "recursion_limit": self.max_iterations,
            },
        )

        return skill_path

    async def analyze_codebase_for_skill(
        self,
        codebase_path: Path,
        skill_name: str,
        output_dir: Path,
    ) -> Path:
        """Analyze a codebase and create a skill from it.

        Args:
            codebase_path: Path to the codebase to analyze
            skill_name: Name for the new skill
            output_dir: Directory to create the skill in

        Returns:
            Path to the created skill
        """
        prompt = f"""Analyze the codebase at {codebase_path} and create a skill named "{skill_name}".

**Task**:
1. Explore the codebase structure using glob and file reading
2. Identify the main purpose and patterns of the code
3. Look for README.md, existing tests, and key source files
4. Extract common patterns, best practices, and workflows
5. Create a skill that captures this knowledge

**Output**: Create the skill at {output_dir / skill_name}

The skill should:
- Have a clear name and description for triggering
- Include key code patterns and examples
- Reference important files and their purposes
- Suggest test cases based on existing tests (if any)
"""

        result = await self.graph.ainvoke(
            {"messages": [HumanMessage(content=prompt)]},
            config={
                "configurable": {"thread_id": f"skill-analyze-{skill_name}"},
                "recursion_limit": self.max_iterations,
            },
        )

        return output_dir / skill_name


def load_skill(skill_name: str, skills_dir: Optional[Path] = None) -> dict[str, Any]:
    """Load a skill from the skills directory.

    Args:
        skill_name: Name of the skill to load
        skills_dir: Optional custom skills directory

    Returns:
        Dict with skill metadata and content
    """
    if skills_dir is None:
        skills_dir = Path(__file__).parent / "skills"

    skill_path = skills_dir / skill_name / "SKILL.md"
    if not skill_path.exists():
        raise FileNotFoundError(f"Skill '{skill_name}' not found at {skill_path}")

    content = skill_path.read_text()

    # Parse frontmatter
    name = skill_name
    description = ""
    body = content

    if content.startswith("---"):
        match = re.match(r"^---\n(.*?)---\n", content, re.DOTALL)
        if match:
            frontmatter = match.group(1)
            for line in frontmatter.split("\n"):
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("description:"):
                    description = line.split(":", 1)[1].strip()
            body = content[match.end() :]

    return {
        "name": name,
        "description": description,
        "body": body,
        "path": str(skill_path),
        "dir": str(skill_path.parent),
    }
