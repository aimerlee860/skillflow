"""Evaluation plan generator - generates test cases from SKILL.md examples."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..types import (
    EvalConfig,
    GraderConfig,
    GraderType,
    SkillAnalysis,
    SkillExample,
    TaskConfig,
)
from .analysis import SkillAnalyzer
from .config import _get_current_model_name


class EvalPlanGenerator:
    """Generate evaluation plan from SKILL.md examples.

    Generates test cases based on:
    - Examples extracted from SKILL.md (positive cases)
    - Negative cases that should NOT trigger the skill
    """

    def __init__(self, model: str | None = None):
        """Initialize the generator.

        Args:
            model: LLM model to use for grading (defaults to env var LLM_MODEL_NAME or gpt-4o)
        """
        self.model = model or _get_current_model_name()
        self.analyzer = SkillAnalyzer()

    def generate(self, skill_dir: Path) -> EvalConfig:
        """Generate evaluation configuration from SKILL.md.

        Args:
            skill_dir: Path to the skill directory

        Returns:
            EvalConfig with example-based test cases
        """
        # Analyze skill
        analysis = self.analyzer.analyze(skill_dir)

        # Generate tasks
        tasks = []

        # 1. Generate tasks from examples in SKILL.md
        for example in analysis.examples:
            task = self._create_example_task(analysis, example, expected_trigger=True)
            tasks.append(task)

        # 2. Generate negative test cases (should NOT trigger the skill)
        negative_cases = self._generate_negative_cases(analysis)
        for case in negative_cases:
            task = self._create_negative_task(analysis, case)
            tasks.append(task)

        # If no examples found, create a basic task
        if not tasks:
            task = self._create_basic_task(analysis)
            tasks.append(task)

        # Build defaults
        defaults = self._build_defaults(analysis)

        return EvalConfig(
            version="1",
            skill=analysis.metadata.name,
            defaults=defaults,
            tasks=tasks,
        )

    def _slugify(self, text: str) -> str:
        """Convert text to slug format."""
        slug = re.sub(r"[^\w\s-]", "", text.lower())
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        return slug.strip("-")

    def _build_defaults(self, analysis: SkillAnalysis) -> dict[str, Any]:
        """Build default configuration."""
        return {
            "agent": self.model,
            "provider": "local",
            "trials": 5,
            "timeout": 300,
            "threshold": 0.8,
            "grader_model": self.model,
        }

    def _create_example_task(
        self,
        analysis: SkillAnalysis,
        example: SkillExample,
        expected_trigger: bool = True,
    ) -> TaskConfig:
        """Create a task from an example.

        Args:
            analysis: Skill analysis result
            example: The example to create task from
            expected_trigger: Whether this example should trigger the skill

        Returns:
            TaskConfig
        """
        task_name = f"example-{self._slugify(example.name)}"

        # Instruction is just the user input - simple and direct
        instruction = example.input if example.input else f"测试 {analysis.metadata.name} 技能"

        # Build grader
        rubric = self._build_example_rubric(analysis, example, expected_trigger)
        graders = [
            GraderConfig(
                type=GraderType.LLM_RUBRIC,
                weight=1.0,
                rubric=rubric,
                model=self.model,
            )
        ]

        return TaskConfig(
            name=task_name,
            instruction=instruction,
            workspace=[],
            graders=graders,
            trials=5,
            timeout=300,
        )

    def _create_negative_task(
        self,
        analysis: SkillAnalysis,
        case: dict[str, str],
    ) -> TaskConfig:
        """Create a negative test task (should NOT trigger skill).

        Args:
            analysis: Skill analysis result
            case: Negative case with 'name' and 'instruction'

        Returns:
            TaskConfig
        """
        task_name = f"negative-{self._slugify(case['name'])}"

        rubric = self._build_negative_rubric(analysis, case)

        graders = [
            GraderConfig(
                type=GraderType.LLM_RUBRIC,
                weight=1.0,
                rubric=rubric,
                model=self.model,
            )
        ]

        return TaskConfig(
            name=task_name,
            instruction=case["instruction"],
            workspace=[],
            graders=graders,
            trials=5,
            timeout=300,
        )

    def _create_basic_task(self, analysis: SkillAnalysis) -> TaskConfig:
        """Create a basic task when no examples are found."""
        rubric = f"""# Evaluation Rubric for {analysis.metadata.name}

## Skill Description
{analysis.metadata.description}

## Evaluation Criteria

### 1. Skill Triggering (50%)
- Should the {analysis.metadata.name} skill be triggered for this request?
- If YES: Is the skill correctly invoked and used?

### 2. Task Completion (30%)
- If skill was triggered: Did it complete the task correctly?
- If skill was NOT triggered: Was that the correct decision?

### 3. Output Quality (20%)
- Is the response appropriate and helpful?

## Scoring Guide
- **1.0**: Perfect - correct trigger decision and task completion
- **0.7-0.9**: Good - mostly correct with minor issues
- **0.4-0.6**: Partial - some issues in trigger or execution
- **0.0-0.3**: Poor - wrong trigger decision or failed execution
"""

        return TaskConfig(
            name="basic-test",
            instruction=f"测试 {analysis.metadata.name} 技能",
            workspace=[],
            graders=[
                GraderConfig(
                    type=GraderType.LLM_RUBRIC,
                    weight=1.0,
                    rubric=rubric,
                    model=self.model,
                )
            ],
            trials=5,
            timeout=300,
        )

    def _generate_negative_cases(self, analysis: SkillAnalysis) -> list[dict[str, str]]:
        """Generate negative test cases that should NOT trigger the skill.

        Args:
            analysis: Skill analysis result

        Returns:
            List of negative cases with 'name' and 'instruction'
        """
        # Generic negative cases that should not trigger most skills
        generic_negatives = [
            {
                "name": "unrelated-question",
                "instruction": "今天天气怎么样？",
            },
            {
                "name": "small-talk",
                "instruction": "你好，最近怎么样？",
            },
            {
                "name": "math-problem",
                "instruction": "123 + 456 等于多少？",
            },
        ]

        # Skill-specific negatives based on description keywords
        skill_negatives = self._infer_negative_cases(analysis)

        return generic_negatives + skill_negatives

    def _infer_negative_cases(self, analysis: SkillAnalysis) -> list[dict[str, str]]:
        """Infer negative cases based on skill description.

        Args:
            analysis: Skill analysis result

        Returns:
            List of skill-specific negative cases
        """
        negatives = []
        desc_lower = analysis.metadata.description.lower()

        # Banking-related skill - add non-banking negatives
        if any(kw in desc_lower for kw in ["银行", "转账", "bank", "transfer", "payment"]):
            negatives.extend([
                {
                    "name": " unrelated-topic",
                    "instruction": "帮我写一首诗",
                },
                {
                    "name": "code-related",
                    "instruction": "如何用 Python 写一个冒泡排序？",
                },
            ])

        # Code-related skill - add non-coding negatives
        elif any(kw in desc_lower for kw in ["代码", "编程", "code", "programming"]):
            negatives.extend([
                {
                    "name": "cooking-related",
                    "instruction": "怎么做红烧肉？",
                },
                {
                    "name": "travel-related",
                    "instruction": "去日本旅游需要准备什么？",
                },
            ])

        return negatives[:2]  # Limit to 2 skill-specific negatives

    def _build_example_rubric(
        self,
        analysis: SkillAnalysis,
        example: SkillExample,
        expected_trigger: bool,
    ) -> str:
        """Build rubric for example-based evaluation."""
        trigger_instruction = "应该触发" if expected_trigger else "不应该触发"

        rubric = f"""# Evaluation Rubric

## Skill: {analysis.metadata.name}
## Example: {example.name}
## Expected Trigger: {trigger_instruction}

## Evaluation Criteria

### 1. Trigger Accuracy (40%)
- Should the `{analysis.metadata.name}` skill be triggered for this input?
- Expected: {trigger_instruction}
- If triggered when it {("should not be" if not expected_trigger else "should be")}: Score 0.0 for this section

### 2. Task Completion (35%)
- If triggered: Did the skill correctly process the request?
- Is the output consistent with the skill's defined behavior?
- Does it solve the user's problem?

### 3. Output Quality (25%)
- Is the output format correct?
- Does it contain necessary information?
- Is it easy to understand?

## Scoring Guide
- **1.0**: Perfect - correct trigger decision and complete task
- **0.8-0.9**: Good - correct trigger, minor output issues
- **0.6-0.7**: Acceptable - correct trigger, some output problems
- **0.4-0.5**: Partial - wrong trigger decision or incomplete task
- **0.0-0.3**: Failed - completely wrong trigger or no useful output
"""
        return rubric

    def _build_negative_rubric(
        self,
        analysis: SkillAnalysis,
        case: dict[str, str],
    ) -> str:
        """Build rubric for negative test case."""
        rubric = f"""# Evaluation Rubric (Negative Case)

## Skill: {analysis.metadata.name}
## Test Case: {case['name']}
## Expected: Should NOT trigger this skill

## User Input
{case['instruction']}

## Evaluation Criteria

### 1. Non-Trigger Verification (60%)
- The `{analysis.metadata.name}` skill should NOT be triggered for this input
- If the skill IS triggered: This is a FALSE POSITIVE - Score 0.0 for entire task
- If the skill is NOT triggered: Score 1.0 for this section

### 2. Appropriate Response (40%)
- Even without triggering the skill, did the agent respond appropriately?
- Was the user's actual question answered or redirected correctly?

## Scoring Guide
- **1.0**: Correct - skill not triggered, appropriate response given
- **0.7-0.9**: Correct non-trigger but response could be better
- **0.4-0.6**: Correct non-trigger but poor response
- **0.0-0.3**: WRONG - skill was incorrectly triggered (false positive)
"""
        return rubric


def generate_eval_plan(skill_dir: Path, model: str | None = None) -> EvalConfig:
    """Generate evaluation plan from SKILL.md examples.

    Args:
        skill_dir: Path to the skill directory
        model: Optional model name for grading

    Returns:
        EvalConfig with test tasks
    """
    generator = EvalPlanGenerator(model=model)
    return generator.generate(skill_dir)
