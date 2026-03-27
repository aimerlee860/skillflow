"""Evaluation plan generator - uses LLM to generate test cases.

All test case generation is done by LLM for maximum flexibility:
1. Extract or generate user inputs from SKILL.md examples
2. Generate expected system responses
3. Generate evolved test cases
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from ..types import (
    EvalConfig,
    GraderConfig,
    GraderType,
    SkillAnalysis,
    TaskConfig,
)
from .analysis import SkillAnalyzer
from .config import _get_current_model_name

# Load environment variables
_project_root = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_project_root / ".env")


@dataclass
class TestCase:
    """Test case with metadata."""

    name: str
    instruction: str  # 用户输入
    expected_trigger: bool  # True = positive, False = negative
    source: str  # "原始-技能提供" | "演化" | "LLM生成"
    expected: str | None = None  # 期望的系统答复

    def __post_init__(self):
        """Validate source."""
        valid_sources = ["原始-技能提供", "演化", "LLM生成"]
        if self.source not in valid_sources:
            raise ValueError(f"Invalid source: {self.source}. Must be one of {valid_sources}")


class EvalPlanGenerator:
    """Generate evaluation plan using LLM."""

    # Number of test cases to generate per category
    NUM_POSITIVE_CASES = 3
    NUM_NEGATIVE_CASES = 2
    NUM_EVOLVED_CASES = 2

    def __init__(
        self,
        model: str | None = None,
        include_skill_md_in_rubric: bool = False,
        num_positive: int = 3,
        num_negative: int = 2,
        num_evolved: int = 2,
    ):
        """Initialize the generator.

        Args:
            model: LLM model to use (defaults to env var LLM_MODEL_NAME or gpt-4o)
            include_skill_md_in_rubric: Whether to include SKILL.md content in rubric.
            num_positive: Number of positive test cases to generate
            num_negative: Number of negative test cases to generate
            num_evolved: Number of evolved test cases to generate
        """
        self.model = model or _get_current_model_name()
        self.include_skill_md_in_rubric = include_skill_md_in_rubric
        self.num_positive = num_positive
        self.num_negative = num_negative
        self.num_evolved = num_evolved
        self.analyzer = SkillAnalyzer()
        self._llm_client = None
        self._skill_md_content: str = ""

    def _load_skill_md_content(self, skill_dir: Path) -> str:
        """Load complete SKILL.md content."""
        skill_md_path = skill_dir / "SKILL.md"
        if skill_md_path.exists():
            return skill_md_path.read_text(encoding="utf-8")
        return ""

    def _get_llm_client(self):
        """Get or create LLM client."""
        if self._llm_client is None:
            try:
                from ..llm.client import get_llm_client
                self._llm_client = get_llm_client(model_name=self.model)
            except Exception:
                return None
        return self._llm_client

    def generate(self, skill_dir: Path) -> EvalConfig:
        """Generate evaluation configuration from SKILL.md."""
        # 1. Load SKILL.md content
        self._skill_md_content = self._load_skill_md_content(skill_dir)

        # 2. Analyze skill for metadata
        analysis = self.analyzer.analyze(skill_dir)

        # 3. Use LLM to generate all test cases
        test_cases = self._llm_generate_all_test_cases(analysis)

        # 4. Convert to tasks
        tasks = [self._create_task(analysis, case) for case in test_cases]

        # 5. Build defaults
        defaults = self._build_defaults(analysis)

        return EvalConfig(
            version="1",
            skill=analysis.metadata.name,
            defaults=defaults,
            tasks=tasks,
        )

    def _llm_generate_all_test_cases(self, analysis: SkillAnalysis) -> list[TestCase]:
        """Use LLM to generate all test cases at once."""
        client = self._get_llm_client()
        if not client:
            return self._fallback_test_cases(analysis)

        prompt = f"""你是一个测试用例生成专家。请基于以下技能定义，生成完整的测试用例集。

# 技能定义 (SKILL.md)

{self._skill_md_content}

---

# 任务

请生成以下类型的测试用例：

## 1. 正向测试用例 ({self.num_positive}个)
- 用户输入应该触发该技能
- 包含典型使用场景
- instruction: 用户的原始输入（不包含任何处理流程、说明等）
- expected: 期望的系统答复内容

## 2. 负向测试用例 ({self.num_negative}个)
- 用户输入不应该触发该技能
- 看起来相关但实际上属于其他领域的问题
- instruction: 用户的原始输入
- expected: "不适用"（负向用例不需要期望答案）

## 3. 演化测试用例 ({self.num_evolved}个)
- 基于正向用例的变体
- 改变数值、表达方式、场景细节
- instruction: 用户的原始输入
- expected: 期望的系统答复内容

---

# 输出格式

请以JSON格式输出，包含一个test_cases数组：

```json
{{
  "test_cases": [
    {{
      "name": "测试用例名称（简短描述）",
      "source": "原始|演化|LLM生成",
      "expected_trigger": true或false,
      "instruction": "用户的原始输入",
      "expected": "期望的系统答复"
    }}
  ]
}}
```

## 要求

1. instruction 只包含用户会说的话，不要包含处理流程、技术细节等
2. expected 是系统应该给用户的答复内容，不是"[期望] 技能被触发"这种描述
3. 确保覆盖技能的核心功能场景
4. 用中文输出

只输出JSON，不要其他内容。"""

        try:
            response = client.chat.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)

            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group())
                test_cases = []

                for tc in data.get("test_cases", []):
                    # Map source to Chinese
                    source_map = {
                        "原始": "原始-技能提供",
                        "演化": "演化",
                        "LLM生成": "LLM生成",
                    }
                    source = source_map.get(tc.get("source", "LLM生成"), "LLM生成")

                    case = TestCase(
                        name=tc.get("name", "未命名"),
                        instruction=tc.get("instruction", ""),
                        expected_trigger=tc.get("expected_trigger", True),
                        source=source,
                        expected=tc.get("expected") if tc.get("expected_trigger", True) else None,
                    )
                    test_cases.append(case)

                return test_cases

        except Exception as e:
            print(f"Warning: LLM test case generation failed: {e}")

        return self._fallback_test_cases(analysis)

    def _fallback_test_cases(self, analysis: SkillAnalysis) -> list[TestCase]:
        """Fallback test cases when LLM is not available."""
        return [
            TestCase(
                name="基本正向测试",
                instruction=f"请使用{analysis.metadata.name}技能帮我处理一个任务",
                expected_trigger=True,
                source="LLM生成",
                expected="系统正确执行了该技能",
            ),
            TestCase(
                name="基本负向测试",
                instruction="今天天气怎么样？",
                expected_trigger=False,
                source="LLM生成",
                expected=None,
            ),
        ]

    def _create_task(self, analysis: SkillAnalysis, case: TestCase) -> TaskConfig:
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
            rubric = self._build_rubric(analysis, case)
            graders.append(GraderConfig(
                type=GraderType.LLM_RUBRIC,
                weight=0.5,
                rubric=rubric,
                model=self.model,
            ))

        return TaskConfig(
            name=task_name,
            instruction=case.instruction,
            expected=case.expected,
            expected_trigger=case.expected_trigger,
            workspace=[],
            graders=graders,
            trials=5,
            timeout=300,
        )

    def _build_rubric(self, analysis: SkillAnalysis, case: TestCase) -> str:
        """Build evaluation rubric for a test case."""
        skill_md_section = ""
        if self.include_skill_md_in_rubric and self._skill_md_content:
            skill_md_section = f"""
## 技能定义
```
{self._skill_md_content[:3000]}
```
"""
        rubric = f"""## 技能
{analysis.metadata.name}

## 触发预期
{"应该触发" if case.expected_trigger else "不应该触发"}

## 用户输入
{case.instruction}

## 期望答复
{case.expected or "无"}

{skill_md_section}
## 评估指标

| 指标 | 权重 | 说明 |
|------|------|------|
| 答复准确性 | 50% | 系统答复与期望答复的核心信息是否一致 |
| 格式正确性 | 30% | 答复格式是否符合技能定义的要求 |
| 完整性 | 20% | 是否包含所有必要信息，无遗漏 |

## 评分标准

| 分数 | 说明 |
|------|------|
| 1.0 | 完全符合：核心信息准确、格式正确、内容完整 |
| 0.7-0.9 | 良好：核心信息正确，格式或细节有小差异 |
| 0.4-0.6 | 部分：有关键信息正确，但有明显错误或遗漏 |
| 0.0-0.3 | 不符合：核心信息错误或缺失 |

## 输出格式

以JSON格式输出评分结果：
{{"score": 0.0-1.0, "reasoning": "评分理由"}}
"""
        return rubric

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
    num_positive: int = 3,
    num_negative: int = 2,
    num_evolved: int = 2,
) -> EvalConfig:
    """Generate evaluation plan using LLM.

    Args:
        skill_dir: Path to the skill directory
        model: Optional model name for generation
        include_skill_md_in_rubric: Whether to include SKILL.md content in rubric.
        num_positive: Number of positive test cases
        num_negative: Number of negative test cases
        num_evolved: Number of evolved test cases

    Returns:
        EvalConfig with test cases
    """
    generator = EvalPlanGenerator(
        model=model,
        include_skill_md_in_rubric=include_skill_md_in_rubric,
        num_positive=num_positive,
        num_negative=num_negative,
        num_evolved=num_evolved,
    )
    return generator.generate(skill_dir)
