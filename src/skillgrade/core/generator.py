"""Smart test case generator - generates tests based on skill profile and plan.

This module implements the final stage of test generation:
1. Takes SkillProfile and TestPlan as input
2. Generates test cases according to specifications
3. Outputs EvalConfig in the standard format
"""

from __future__ import annotations

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from ..types import (
    DifficultyLevel,
    EvalConfig,
    GraderConfig,
    GraderType,
    SkillAnalysis,
    SkillExample,
    SkillInfo,
    SkillProfile,
    TaskConfig,
    TestCaseSpec,
    TestPlan,
    TestType,
)
from .analysis import SkillAnalyzer
from .config import _get_current_model_name
from .context import SkillContext, SkillContextExtractor
from .planning import TestPlanner
from .understanding import SkillUnderstandingAnalyzer
from prompts import PromptManager

# Load environment variables
_project_root = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_project_root / ".env")

console = Console()


@dataclass
class TestCase:
    """Test case with metadata."""

    name: str
    instruction: str  # 用户输入
    expected_trigger: bool  # True = positive, False = negative
    source: str  # "原始-技能提供" | "演化" | "LLM生成" | "边界测试-*"
    expected: str | None = None  # 期望的系统答复

    # Difficulty info (populated during generation)
    difficulty: DifficultyLevel | None = None
    difficulty_reasoning: str | None = None

    def __post_init__(self):
        """Validate source."""
        valid_sources = [
            "原始-技能提供", "演化", "LLM生成",
            "边界测试-数值", "边界测试-完整性", "边界测试-格式", "边界测试-业务", "边界测试"
        ]
        if self.source not in valid_sources and not self.source.startswith("边界测试"):
            pass  # Allow unknown sources for backward compatibility


class TestCaseGenerator:
    """Generates test cases based on skill profile and test plan.

    This is the final stage of the smart generation pipeline:
    - Input: SkillProfile, TestPlan
    - Output: EvalConfig
    """

    # Test type to source mapping
    TYPE_SOURCE_MAP = {
        TestType.POSITIVE: "LLM生成",
        TestType.NEGATIVE: "LLM生成",
        TestType.EVOLVED: "演化",
        TestType.BOUNDARY: "边界测试",
    }

    # Boundary type translation
    BOUNDARY_TYPE_MAP = {
        "numeric": "数值",
        "completeness": "完整性",
        "format": "格式",
        "business": "业务",
    }

    def __init__(
        self,
        model: str | None = None,
        include_skill_md_in_rubric: bool = False,
        parallel: int = 4,
    ):
        """Initialize the generator.

        Args:
            model: LLM model to use
            include_skill_md_in_rubric: Whether to include SKILL.md in rubric
            parallel: Number of parallel threads for test case generation (default: 4)
        """
        self.model = model or _get_current_model_name()
        self.include_skill_md_in_rubric = include_skill_md_in_rubric
        self.parallel = max(1, parallel)
        self.analyzer = SkillAnalyzer()
        self._llm_client = None
        self._skill_md_content: str = ""
        self._skill_context: SkillContext | None = None

    def _get_llm_client(self):
        """Get or create LLM client."""
        if self._llm_client is None:
            try:
                from ..llm.client import get_llm_client, validate_llm_config
                if not validate_llm_config():
                    console.print("[yellow]Warning: LLM configuration invalid. Set LLM_BASE_URL and LLM_API_KEY.[/yellow]")
                    return None
                self._llm_client = get_llm_client(model_name=self.model)
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to create LLM client: {e}[/yellow]")
                return None
        return self._llm_client

    def _load_skill_md_content(self, skill_dir: Path) -> str:
        """Load complete SKILL.md content."""
        skill_md_path = skill_dir / "SKILL.md"
        if skill_md_path.exists():
            return skill_md_path.read_text(encoding="utf-8")
        return ""

    def generate(
        self,
        skill_dir: Path,
        profile: SkillProfile,
        plan: TestPlan,
    ) -> EvalConfig:
        """Generate evaluation configuration from profile and plan.

        Args:
            skill_dir: Path to skill directory
            profile: Skill analysis result
            plan: Test plan with specifications

        Returns:
            EvalConfig with test tasks
        """
        # Load skill content
        self._skill_md_content = self._load_skill_md_content(skill_dir)

        # Extract skill context
        skill_md_path = skill_dir / "SKILL.md"
        context_extractor = SkillContextExtractor()
        self._skill_context = context_extractor.extract(skill_md_path)

        # Analyze skill for metadata
        analysis = self.analyzer.analyze(skill_dir)

        # Generate test cases from plan
        test_cases, example_count, llm_count = self._generate_test_cases(profile, plan, analysis)

        # Convert to tasks (pass profile for skill summary)
        tasks = [self._create_task(analysis, case, profile) for case in test_cases]

        # Build skill info and settings
        # Use LLM-generated summary from profile, fallback to metadata description
        skill_summary = profile.summary or analysis.metadata.description
        skill_info = SkillInfo(
            name=analysis.metadata.name,
            summary=skill_summary,
        )
        settings = self._build_defaults(analysis)

        return EvalConfig(
            skill=skill_info,
            settings=settings,
            tasks=tasks,
        )

    def _generate_test_cases(
        self,
        profile: SkillProfile,
        plan: TestPlan,
        analysis: SkillAnalysis,
    ) -> tuple[list[TestCase], int, int]:
        """Generate test cases from plan specifications.

        Uses parallel generation for efficiency.
        All test cases are generated by LLM for consistency.
        """
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
        )

        cases = []
        llm_generated_count = 0
        example_count = 0

        llm_client = self._get_llm_client()

        if llm_client and self._skill_context:
            # 1. 使用 LLM 从 SKILL.md 示例中提取和生成测试用例
            if analysis.examples:
                console.print(f"[cyan]使用 LLM 从 SKILL.md 示例生成测试用例...[/cyan]")
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[cyan]{task.description}[/cyan]"),
                    BarColumn(complete_style="green", finished_style="green"),
                    MofNCompleteColumn(),
                    TaskProgressColumn(),
                    TimeElapsedColumn(),
                    console=console,
                    transient=True,
                ) as progress:
                    task = progress.add_task("从示例生成", total=len(analysis.examples))
                    for example in analysis.examples:
                        llm_case = self._generate_case_from_skill_example(example, analysis)
                        if llm_case:
                            cases.append(llm_case)
                            example_count += 1
                        progress.advance(task)

                if example_count > 0:
                    console.print(f"[dim]从 SKILL.md 示例生成 {example_count} 个测试用例[/dim]")

            # 2. Generate cases from plan specs using LLM (parallel)
            total_specs = len(plan.cases)
            console.print(f"[cyan]使用 LLM 并行生成 {total_specs} 个测试用例 (并发数: {self.parallel})...[/cyan]")

            # Generate in parallel with progress bar
            generated_cases = self._generate_cases_parallel(plan.cases, analysis)

            # Add successfully generated cases
            for case in generated_cases:
                if case:
                    cases.append(case)
                    llm_generated_count += 1

        # 3. If LLM failed to generate any cases, use fallback
        if len(cases) == 0:
            console.print("[yellow]LLM 生成失败，使用备用用例...[/yellow]")
            cases = self._fallback_cases(analysis)

        # Print final summary
        total = len(cases)
        if example_count > 0:
            console.print(f"[bold]实际生成 {total} 个测试用例[/bold] [dim](示例: {example_count}, LLM生成: {llm_generated_count})[/dim]")
        else:
            console.print(f"[bold]实际生成 {total} 个测试用例[/bold]")

        return cases, example_count, llm_generated_count

    def _generate_cases_parallel(
        self,
        specs: list[TestCaseSpec],
        analysis: SkillAnalysis,
    ) -> list[TestCase | None]:
        """Generate test cases in parallel using ThreadPoolExecutor.

        Args:
            specs: List of test case specifications
            analysis: Skill analysis result

        Returns:
            List of generated test cases (None for failed generations)
        """
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
        )

        results: list[TestCase | None] = [None] * len(specs)
        completed_count = 0
        success_count = 0
        lock = threading.Lock()

        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]{task.description}[/cyan]"),
            BarColumn(complete_style="green", finished_style="green"),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("生成测试用例", total=len(specs))

            with ThreadPoolExecutor(max_workers=self.parallel) as executor:
                # Submit all tasks
                future_to_index = {
                    executor.submit(self._generate_single_case, spec, analysis): i
                    for i, spec in enumerate(specs)
                }

                # Collect results as they complete
                for future in as_completed(future_to_index):
                    index = future_to_index[future]
                    try:
                        case = future.result()
                        results[index] = case
                        with lock:
                            completed_count += 1
                            if case:
                                success_count += 1
                        progress.update(task, completed=completed_count)
                    except Exception:
                        with lock:
                            completed_count += 1
                        results[index] = None
                        progress.update(task, completed=completed_count)

        # Print results summary
        console.print(f"[dim]成功: {success_count}/{len(specs)}[/dim]")

        # Print generated case names
        for i, case in enumerate(results):
            if case:
                console.print(f"  [green]✓[/green] {case.name}")

        return results

    def _generate_single_case(
        self,
        spec: TestCaseSpec,
        analysis: SkillAnalysis,
    ) -> TestCase | None:
        """Generate a single test case based on specification."""
        llm_client = self._get_llm_client()
        if not llm_client or not self._skill_context:
            return None

        # Build prompt for single case generation
        prompt = self._build_single_case_prompt(spec)

        try:
            response = llm_client.chat.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            return self._parse_single_case(content, spec)
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to generate test case {spec.id}: {e}[/yellow]")
            return None

    def _generate_case_from_skill_example(
        self,
        example: "SkillExample",
        analysis: SkillAnalysis,
    ) -> TestCase | None:
        """Generate a complete test case from a SKILL.md example using LLM.

        The LLM will:
        1. Extract the user instruction (only user input, no processing steps)
        2. Generate a detailed expected output
        3. Determine the difficulty level

        Args:
            example: The example from SKILL.md
            analysis: Skill analysis result

        Returns:
            TestCase with complete instruction and expected output
        """
        llm_client = self._get_llm_client()
        if not llm_client or not self._skill_context:
            return None

        prompt = PromptManager.get(
            "skillgrade/example_extraction",
            skill_context=self._skill_context.to_full_context(),
            example_name=example.name,
            example_input=example.input,
            example_expected_output=example.expected_output or "",
        )

        try:
            response = llm_client.chat.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)

            # Create a dummy spec for parsing
            dummy_spec = TestCaseSpec(
                id=f"example-{example.name}",
                test_type=TestType.POSITIVE,
                difficulty_target=DifficultyLevel.EASY,
                description=f"从 SKILL.md 示例生成",
            )
            case = self._parse_single_case(content, dummy_spec)
            if case:
                case.source = "原始-技能提供"
            return case
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to generate test case from example: {e}[/yellow]")
            return None

    def _build_single_case_prompt(self, spec: TestCaseSpec) -> str:
        """Build prompt for generating a single test case."""
        type_names = {
            TestType.POSITIVE: "正向测试",
            TestType.NEGATIVE: "负向测试",
            TestType.EVOLVED: "演化测试",
            TestType.BOUNDARY: "边界测试",
        }

        difficulty_names = {
            DifficultyLevel.EASY: "简单",
            DifficultyLevel.MEDIUM: "中等",
            DifficultyLevel.HARD: "困难",
        }

        difficulty_hints = {
            DifficultyLevel.EASY: "信息完整，用户提供了所有必要信息，可直接执行",
            DifficultyLevel.MEDIUM: "部分信息缺失，需要简单推理或追问",
            DifficultyLevel.HARD: "关键信息严重缺失，表达模糊，需要多轮交互",
        }

        test_type_desc = {
            TestType.POSITIVE: "用户输入应该触发该技能，系统应返回正确处理结果",
            TestType.NEGATIVE: "用户输入不应该触发该技能，属于其他领域的问题",
            TestType.EVOLVED: "基于典型用例的变体，改变数值、表达方式或场景细节",
            TestType.BOUNDARY: "测试边界条件，如数值极限、格式错误、信息缺失等",
        }

        boundary_hint = ""
        if spec.test_type == TestType.BOUNDARY and spec.boundary_type:
            boundary_cn = self.BOUNDARY_TYPE_MAP.get(spec.boundary_type, spec.boundary_type)
            boundary_hint = f"\n边界类型: {boundary_cn}"

        function_hint = ""
        if spec.target_function:
            function_hint = f"\n目标功能: {spec.target_function}"

        return PromptManager.get(
            "skillgrade/test_case_generation",
            skill_context=self._skill_context.to_full_context(),
            test_type_name=type_names.get(spec.test_type, "正向测试"),
            difficulty_name=difficulty_names.get(spec.difficulty_target, "中等"),
            function_hint=function_hint,
            boundary_hint=boundary_hint,
            test_type_description=test_type_desc.get(spec.test_type, "正向测试"),
            difficulty_easy=difficulty_hints[DifficultyLevel.EASY],
            difficulty_medium=difficulty_hints[DifficultyLevel.MEDIUM],
            difficulty_hard=difficulty_hints[DifficultyLevel.HARD],
            difficulty_description=difficulty_hints.get(spec.difficulty_target, difficulty_hints[DifficultyLevel.MEDIUM]),
        )

    def _parse_single_case(
        self,
        content: str,
        spec: TestCaseSpec,
    ) -> TestCase | None:
        """Parse LLM response to TestCase."""
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return None

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return None

        instruction = data.get("instruction", "")
        if not instruction:
            return None

        # Determine source
        source = self.TYPE_SOURCE_MAP.get(spec.test_type, "LLM生成")
        if spec.test_type == TestType.BOUNDARY and spec.boundary_type:
            boundary_cn = self.BOUNDARY_TYPE_MAP.get(spec.boundary_type, spec.boundary_type)
            source = f"边界测试-{boundary_cn}"

        # Parse difficulty
        difficulty_str = data.get("difficulty", "medium").lower()
        difficulty_map = {
            "easy": DifficultyLevel.EASY,
            "medium": DifficultyLevel.MEDIUM,
            "hard": DifficultyLevel.HARD,
        }
        difficulty = difficulty_map.get(difficulty_str, spec.difficulty_target)

        # Handle expected
        expected = data.get("expected")
        expected_trigger = data.get("expected_trigger", True)
        if not expected_trigger or expected == "不适用":
            expected = None

        return TestCase(
            name=data.get("name", spec.description),
            instruction=instruction,
            expected_trigger=expected_trigger,
            source=source,
            expected=expected,
            difficulty=difficulty,
            difficulty_reasoning=data.get("difficulty_reasoning", ""),
        )

    def _fallback_cases(self, analysis: SkillAnalysis) -> list[TestCase]:
        """Fallback test cases when LLM is not available."""
        return [
            TestCase(
                name="基本正向测试",
                instruction=f"请使用{analysis.metadata.name}技能帮我处理一个任务",
                expected_trigger=True,
                source="LLM生成",
                expected="系统正确执行了该技能",
                difficulty=DifficultyLevel.EASY,
            ),
            TestCase(
                name="基本负向测试",
                instruction="今天天气怎么样？",
                expected_trigger=False,
                source="LLM生成",
                expected=None,
                difficulty=DifficultyLevel.EASY,
            ),
        ]

    def _create_task(
        self,
        analysis: SkillAnalysis,
        case: TestCase,
        profile: SkillProfile,
    ) -> TaskConfig:
        """Create a TaskConfig from a TestCase."""
        task_name = self._slugify(case.name)

        graders = []

        # 1. Trigger grader (checks if skill was triggered)
        graders.append(GraderConfig(
            type=GraderType.TRIGGER,
            weight=0.5,
            expected_trigger=case.expected_trigger,
        ))

        # 2. LLM rubric grader (only for positive cases with expected output)
        if case.expected_trigger and case.expected:
            # rubric 包含大模型生成的特殊评估要求，如果没有则为 None
            rubric = self._build_rubric(case)
            graders.append(GraderConfig(
                type=GraderType.LLM,
                weight=0.5,
                rubric=rubric,
                model=self.model,
            ))

        return TaskConfig(
            name=task_name,
            instruction=case.instruction,
            expected=case.expected,
            trigger=case.expected_trigger,  # 使用新的 trigger 字段
            workspace=[],
            graders=graders,
            trials=5,
            timeout=300,
        )

    def _build_rubric(self, case: TestCase) -> str | None:
        """Build special evaluation details for a test case.

        只生成特例化的评估细节，完整的评估标准由统一模板在评估时拼接。
        如果没有额外的评估细则，返回 None。

        Args:
            case: TestCase with instruction, expected output, etc.

        Returns:
            特例化的评估细节字符串，或 None
        """
        # 目前不生成特例化评估细节，返回 None
        # 完整的评估标准由 LLMGrader 在评估时使用统一模板拼接
        return None

    def _slugify(self, text: str) -> str:
        """Convert text to slug format."""
        slug = re.sub(r"[^\w\s-]", "", text.lower())
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        return slug.strip("-")

    def _build_defaults(self, analysis: SkillAnalysis) -> dict[str, Any]:
        """Build default configuration."""
        return {
            "trials": 5,
            "timeout": 300,
            "threshold": 0.8,
        }


def generate_eval_plan(
    skill_dir: Path,
    model: str | None = None,
    include_skill_md_in_rubric: bool = False,
    parallel: int = 4,
    # Removed: num_positive, num_negative, num_evolved, num_boundary
    # Now uses smart planning based on skill complexity
) -> EvalConfig:
    """Generate evaluation plan using smart test planning.

    This function analyzes the skill's complexity and characteristics,
    then automatically determines the appropriate number and type of
    test cases to generate.

    Args:
        skill_dir: Path to the skill directory
        model: Optional LLM model for generation
        include_skill_md_in_rubric: Whether to include SKILL.md in rubric
        parallel: Number of parallel threads for generation (default: 4)

    Returns:
        EvalConfig with intelligently planned test cases
    """
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]{task.description}[/cyan]"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        # Stage 1: Understand the skill
        task1 = progress.add_task("分析技能复杂度和核心功能...", total=None)
        analyzer = SkillUnderstandingAnalyzer(model=model)
        profile = analyzer.analyze(skill_dir)
        progress.update(task1, completed=True)

        console.print(f"[bold]技能复杂度:[/bold] {profile.complexity.value}, [bold]核心功能:[/bold] {len(profile.core_functions)}个")

        # Stage 2: Plan tests
        task2 = progress.add_task("规划测试用例分布...", total=None)
        planner = TestPlanner()
        plan = planner.plan(profile)
        progress.update(task2, completed=True)

        console.print(f"[bold]计划生成 {plan.total_count} 个测试用例[/bold]")
        console.print(f"  [dim]类型分布:[/dim] {', '.join(f'{k.value}={v}' for k, v in plan.type_distribution.items())}")
        console.print(f"  [dim]难度分布:[/dim] {', '.join(f'{k.value}={v}' for k, v in plan.difficulty_distribution.items())}")

    # Stage 3: Generate tests (parallel) - has its own progress bar
    generator = TestCaseGenerator(
        model=model,
        include_skill_md_in_rubric=include_skill_md_in_rubric,
        parallel=parallel,
    )
    config = generator.generate(skill_dir, profile, plan)

    return config
