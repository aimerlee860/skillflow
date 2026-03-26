"""Evaluation plan generator - generates test cases using three-layer strategy.

Three-layer test case generation:
1. Original examples from SKILL.md (marked as "原始-技能提供")
2. Evolved examples from original (marked as "演化")
3. LLM-generated examples based on skill understanding (marked as "LLM生成")
"""

from __future__ import annotations

import asyncio
import os
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
    SkillExample,
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
    instruction: str
    expected_trigger: bool  # True = positive, False = negative
    source: str  # "原始-技能提供" | "演化" | "LLM生成"
    expected: str | None = None  # 期望结果（用于输出对比）

    def __post_init__(self):
        """Validate source."""
        valid_sources = ["原始-技能提供", "演化", "LLM生成"]
        if self.source not in valid_sources:
            raise ValueError(f"Invalid source: {self.source}. Must be one of {valid_sources}")


class EvalPlanGenerator:
    """Generate evaluation plan using three-layer test case strategy."""

    # Evolution times
    EVOLUTION_TIMES = 3

    def __init__(self, model: str | None = None):
        """Initialize the generator.

        Args:
            model: LLM model to use (defaults to env var LLM_MODEL_NAME or gpt-4o)
        """
        self.model = model or _get_current_model_name()
        self.analyzer = SkillAnalyzer()
        self._llm_client = None
        self._skill_md_content: str = ""  # 缓存完整 SKILL.md 内容

    def _load_skill_md_content(self, skill_dir: Path) -> str:
        """Load complete SKILL.md content for expected generation.

        Args:
            skill_dir: Path to the skill directory

        Returns:
            Complete SKILL.md content as string
        """
        skill_md_path = skill_dir / "SKILL.md"
        if skill_md_path.exists():
            return skill_md_path.read_text(encoding="utf-8")
        return ""

    def generate(self, skill_dir: Path) -> EvalConfig:
        """Generate evaluation configuration from SKILL.md.

        Args:
            skill_dir: Path to the skill directory

        Returns:
            EvalConfig with three-layer test cases
        """
        # 1. 加载完整 SKILL.md 内容（用于生成期望答案）
        self._skill_md_content = self._load_skill_md_content(skill_dir)

        # 2. Analyze skill
        analysis = self.analyzer.analyze(skill_dir)

        # 3. Generate test cases with expected results
        positive_cases = self._generate_positive_cases(analysis)
        negative_cases = self._generate_negative_cases(analysis)

        # 4. Convert to tasks
        tasks = []
        for case in positive_cases:
            task = self._create_task(analysis, case)
            tasks.append(task)
        for case in negative_cases:
            task = self._create_task(analysis, case)
            tasks.append(task)

        # 5. Build defaults
        defaults = self._build_defaults(analysis)

        return EvalConfig(
            version="1",
            skill=analysis.metadata.name,
            defaults=defaults,
            tasks=tasks,
        )

    def _generate_positive_cases(self, analysis: SkillAnalysis) -> list[TestCase]:
        """Generate positive test cases (should trigger skill).

        Three-layer strategy:
        1. Original examples from SKILL.md
        2. Evolved from original examples
        3. LLM-generated based on skill understanding
        """
        cases = []

        # Layer 1: Original examples
        for example in analysis.examples:
            # 生成期望结果
            expected = example.expected_output or self._llm_generate_expected(
                analysis, example.input
            )
            cases.append(TestCase(
                name=f"原始-{example.name}",
                instruction=example.input,
                expected_trigger=True,
                source="原始-技能提供",
                expected=expected,
            ))

        # Layer 2: Evolved from original examples
        if analysis.examples:
            evolved = self._evolve_examples(analysis, analysis.examples, expected_trigger=True)
            cases.extend(evolved)

        # Layer 3: LLM-generated positive cases
        llm_cases = self._llm_generate_cases(analysis, expected_trigger=True)
        cases.extend(llm_cases)

        return cases

    def _generate_negative_cases(self, analysis: SkillAnalysis) -> list[TestCase]:
        """Generate negative test cases (should NOT trigger skill).

        Three-layer strategy:
        1. Original negative examples (if any in SKILL.md)
        2. Evolved negative cases
        3. LLM-generated negative cases
        """
        cases = []

        # Layer 1: Original negative examples (usually none in SKILL.md)
        # For now, we skip this as SKILL.md typically doesn't have negative examples

        # Layer 2: Generate negative cases by evolving/inverting positive examples
        if analysis.examples:
            evolved_negatives = self._evolve_to_negative(analysis, analysis.examples)
            # 为负向用例设置固定期望
            for case in evolved_negatives:
                case.expected = "问题与本技能无关，SKILL.md 不应被读取"
            cases.extend(evolved_negatives)

        # Layer 3: LLM-generated negative cases
        llm_cases = self._llm_generate_cases(analysis, expected_trigger=False)
        # 为负向用例设置固定期望
        for case in llm_cases:
            case.expected = "问题与本技能无关，SKILL.md 不应被读取"
        cases.extend(llm_cases)

        return cases

    def _evolve_examples(
        self,
        analysis: SkillAnalysis,
        examples: list[SkillExample],
        expected_trigger: bool,
    ) -> list[TestCase]:
        """Evolve examples to create new test cases.

        Args:
            analysis: Skill analysis
            examples: Original examples
            expected_trigger: Whether evolved cases should trigger skill

        Returns:
            List of evolved test cases
        """
        if not examples:
            return []

        evolved = []

        # Use LLM to evolve each example
        for example in examples:
            try:
                evolved_cases = self._llm_evolve_example(analysis, example, expected_trigger)
                evolved.extend(evolved_cases)
            except Exception as e:
                # Fallback: simple variations if LLM fails
                fallback = self._simple_evolve(example, expected_trigger)
                evolved.extend(fallback)

        return evolved[:self.EVOLUTION_TIMES * len(examples)]  # Limit to N evolutions per example

    def _llm_evolve_example(
        self,
        analysis: SkillAnalysis,
        example: SkillExample,
        expected_trigger: bool,
    ) -> list[TestCase]:
        """Use LLM to evolve an example into new test cases."""
        client = self._get_llm_client()
        if not client:
            return self._simple_evolve(example, expected_trigger)

        trigger_desc = "应该触发" if expected_trigger else "不应该触发"

        prompt = f"""你是一个测试用例生成专家。请基于以下原始示例，演化生成 {self.EVOLUTION_TIMES} 个新的测试用例。

技能名称: {analysis.metadata.name}
技能描述: {analysis.metadata.description}

原始示例:
- 名称: {example.name}
- 用户输入: {example.input}

要求:
1. 新测试用例应该{trigger_desc}该技能
2. 保持测试意图相似，但改变具体场景、数值、表达方式
3. 每个测试用例应该有不同的边界情况或场景变化
4. 用中文输出

请以JSON数组格式输出，每个测试用例包含name和instruction字段:
[{{"name": "名称", "instruction": "用户输入"}}]"""

        try:
            import json
            response = client.chat.invoke(prompt)
            content = response.content

            # Extract JSON from response
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                cases_data = json.loads(json_match.group())
                return [
                    TestCase(
                        name=f"演化-{case['name']}",
                        instruction=case['instruction'],
                        expected_trigger=expected_trigger,
                        source="演化",
                    )
                    for case in cases_data
                ]
        except Exception as e:
            print(f"Warning: LLM evolution failed: {e}")

        return self._simple_evolve(example, expected_trigger)

    def _simple_evolve(
        self,
        example: SkillExample,
        expected_trigger: bool,
    ) -> list[TestCase]:
        """Simple fallback evolution without LLM."""
        # Generate simple variations
        variations = []

        # Variation 1: Change numbers/amounts
        import re
        new_instruction = re.sub(r'\d+', lambda m: str(int(m.group()) * 2), example.input)
        if new_instruction != example.input:
            variations.append(TestCase(
                name=f"演化-{example.name}-变体1",
                instruction=new_instruction,
                expected_trigger=expected_trigger,
                source="演化",
            ))

        # Variation 2: Add more context
        variations.append(TestCase(
            name=f"演化-{example.name}-变体2",
            instruction=f"请帮我处理一下：{example.input}",
            expected_trigger=expected_trigger,
            source="演化",
        ))

        return variations

    def _evolve_to_negative(
        self,
        analysis: SkillAnalysis,
        examples: list[SkillExample],
    ) -> list[TestCase]:
        """Evolve positive examples into negative cases (should NOT trigger).

        This creates edge cases that are similar to positive cases but
        should NOT trigger the skill.
        """
        if not examples:
            return []

        negative_cases = []

        for example in examples:
            try:
                evolved = self._llm_evolve_to_negative(analysis, example)
                negative_cases.extend(evolved)
            except Exception:
                # Fallback: use skill-specific negatives
                pass

        return negative_cases[:3]  # Limit to 3 evolved negatives

    def _llm_evolve_to_negative(
        self,
        analysis: SkillAnalysis,
        example: SkillExample,
    ) -> list[TestCase]:
        """Use LLM to create negative cases from positive example."""
        client = self._get_llm_client()
        if not client:
            return []

        prompt = f"""你是一个测试用例生成专家。请基于以下正向示例，生成2个负向测试用例（不应该触发该技能的输入）。

技能名称: {analysis.metadata.name}
技能描述: {analysis.metadata.description}

正向示例:
- 用户输入: {example.input}

要求:
1. 生成的输入看起来相关但实际上不应该触发该技能
2. 可以是：边界情况、相似但不同的任务、无关的请求
3. 用中文输出

请以JSON数组格式输出:
[{{"name": "名称", "instruction": "用户输入", "reason": "为什么不应该触发"}}]"""

        try:
            import json
            response = client.chat.invoke(prompt)
            content = response.content

            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                cases_data = json.loads(json_match.group())
                return [
                    TestCase(
                        name=f"演化负向-{case['name']}",
                        instruction=case['instruction'],
                        expected_trigger=False,
                        source="演化",
                    )
                    for case in cases_data
                ]
        except Exception as e:
            print(f"Warning: LLM negative evolution failed: {e}")

        return []

    def _llm_generate_cases(
        self,
        analysis: SkillAnalysis,
        expected_trigger: bool,
    ) -> list[TestCase]:
        """Use LLM to generate test cases based on skill understanding.

        Args:
            analysis: Skill analysis
            expected_trigger: Whether cases should trigger skill

        Returns:
            List of LLM-generated test cases
        """
        client = self._get_llm_client()
        if not client:
            # Fallback to rule-based generation
            if expected_trigger:
                return self._rule_based_positive(analysis)
            else:
                return self._rule_based_negative(analysis)

        trigger_desc = "应该触发" if expected_trigger else "不应该触发"
        case_type = "正向" if expected_trigger else "负向"

        # Build skill context
        skill_context = f"""
技能名称: {analysis.metadata.name}
技能描述: {analysis.metadata.description}
"""
        if analysis.use_cases:
            skill_context += f"\n使用场景:\n" + "\n".join(f"- {uc}" for uc in analysis.use_cases[:3])
        if analysis.core_functions:
            skill_context += f"\n核心功能:\n" + "\n".join(f"- {cf}" for cf in analysis.core_functions[:3])

        prompt = f"""你是一个测试用例生成专家。请为以下技能生成3个{case_type}测试用例。

{skill_context}

要求:
1. 测试用例{"应该触发" if expected_trigger else "不应该触发"}该技能
2. {"模拟真实用户请求该技能的场景" if expected_trigger else "生成看起来相关但实际上不应该触发该技能的输入"}
3. 用中文输出
4. 每个测试用例应该有不同的场景和边界情况

请以JSON数组格式输出:
[{{"name": "名称", "instruction": "用户输入"}}]"""

        try:
            import json
            response = client.chat.invoke(prompt)
            content = response.content

            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                cases_data = json.loads(json_match.group())
                test_cases = []
                for case in cases_data:
                    tc = TestCase(
                        name=f"LLM生成-{case['name']}",
                        instruction=case['instruction'],
                        expected_trigger=expected_trigger,
                        source="LLM生成",
                        expected=None,  # 先创建用例，后面统一生成期望
                    )
                    test_cases.append(tc)

                # 为正向用例生成期望结果
                if expected_trigger:
                    for tc in test_cases:
                        tc.expected = self._llm_generate_expected(analysis, tc)

                return test_cases
        except Exception as e:
            print(f"Warning: LLM generation failed: {e}")

        # Fallback
        if expected_trigger:
            cases = self._rule_based_positive(analysis)
            for case in cases:
                case.expected = self._llm_generate_expected(analysis, case)
            return cases
        else:
            return self._rule_based_negative(analysis)

    def _rule_based_positive(self, analysis: SkillAnalysis) -> list[TestCase]:
        """Rule-based positive case generation (fallback)."""
        cases = []
        desc_lower = analysis.metadata.description.lower()

        if any(kw in desc_lower for kw in ["银行", "转账", "bank", "transfer"]):
            cases.append(TestCase(
                name="LLM生成-转账请求",
                instruction="我要给朋友转账3000元",
                expected_trigger=True,
                source="LLM生成",
            ))
        elif any(kw in desc_lower for kw in ["代码", "code", "编程"]):
            cases.append(TestCase(
                name="LLM生成-代码请求",
                instruction="帮我写一个函数",
                expected_trigger=True,
                source="LLM生成",
            ))
        else:
            cases.append(TestCase(
                name="LLM生成-基本请求",
                instruction=f"请使用{analysis.metadata.name}技能帮我处理一个任务",
                expected_trigger=True,
                source="LLM生成",
            ))

        return cases

    def _rule_based_negative(self, analysis: SkillAnalysis) -> list[TestCase]:
        """Rule-based negative case generation (fallback)."""
        return [
            TestCase(
                name="LLM生成-无关问题",
                instruction="今天天气怎么样？",
                expected_trigger=False,
                source="LLM生成",
            ),
            TestCase(
                name="LLM生成-闲聊",
                instruction="你好，最近怎么样？",
                expected_trigger=False,
                source="LLM生成",
            ),
        ]

    def _get_llm_client(self):
        """Get or create LLM client."""
        if self._llm_client is None:
            try:
                from ..llm.client import get_llm_client
                self._llm_client = get_llm_client(model_name=self.model)
            except Exception:
                return None
        return self._llm_client

    def _create_task(self, analysis: SkillAnalysis, case: TestCase) -> TaskConfig:
        """Create a TaskConfig from a TestCase."""
        task_name = self._slugify(case.name)

        graders = []

        # 1. 触发验证评估器（确定性，基于 SKILL.md 是否被读取）
        graders.append(GraderConfig(
            type=GraderType.TRIGGER,
            weight=0.5,
            expected_trigger=case.expected_trigger,
        ))

        # 2. 对于正向测试，添加输出对比评估器
        if case.expected_trigger:
            rubric = self._build_positive_rubric(analysis, case)
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
        if case.expected_trigger:
            return self._build_positive_rubric(analysis, case)
        else:
            return self._build_negative_rubric(analysis, case)

    def _build_positive_rubric(self, analysis: SkillAnalysis, case: TestCase) -> str:
        """Build rubric for positive test case."""
        source_display = {
            "原始-技能提供": "原始示例（来自SKILL.md）",
            "演化": "演化测试用例",
            "LLM生成": "LLM生成测试用例",
        }.get(case.source, case.source)

        # 包含期望结果
        expected_section = ""
        if case.expected:
            expected_section = f"""
## 期望输出
{case.expected}
"""

        # 包含 SKILL.md 内容（限制长度）
        skill_md_section = ""
        if self._skill_md_content:
            skill_md_truncated = self._skill_md_content[:3000]
            skill_md_section = f"""
## 技能定义 (SKILL.md 参考)
```
{skill_md_truncated}
```
"""

        rubric = f"""# 评估标准 (正向测试)

## 技能: {analysis.metadata.name}
## 测试用例来源: {source_display}
## 预期: 应该触发此技能

## 用户输入
{case.instruction}
{expected_section}
{skill_md_section}

## 评估标准

### 1. 核心信息匹配 (60%)
- 关键数据是否正确（如金额、账号、日期等）
- 主要结论是否一致
- 核心操作是否完成

### 2. 格式正确性 (20%)
- 输出格式是否符合技能定义要求
- 是否包含所有必要字段
- 结构是否清晰

### 3. 完整性 (20%)
- 是否遗漏重要信息
- 是否有多余内容
- 逻辑是否连贯

## 评分指南
- **1.0**: 完全匹配 - 核心信息准确，格式正确，内容完整
- **0.7-0.9**: 良好 - 核心信息正确，格式有小差异
- **0.4-0.6**: 部分匹配 - 有一些错误或遗漏
- **0.0-0.3**: 严重不匹配 - 核心信息错误或缺失

## 输出要求
以 JSON 格式输出评分结果：
{{"score": 0.0-1.0, "reasoning": "评分理由"}}
"""
        return rubric

    def _build_negative_rubric(self, analysis: SkillAnalysis, case: TestCase) -> str:
        """Build rubric for negative test case."""
        source_display = {
            "原始-技能提供": "原始示例（来自SKILL.md）",
            "演化": "演化测试用例",
            "LLM生成": "LLM生成测试用例",
        }.get(case.source, case.source)

        rubric = f"""# 评估标准 (负向测试)

## 技能: {analysis.metadata.name}
## 测试用例来源: {source_display}
## 预期: 不应该触发此技能

## 用户输入
{case.instruction}

## 评估标准

### 1. 非触发验证 (60%)
- `{analysis.metadata.name}` 技能不应该被触发
- 如果技能被触发: 这是假阳性 - 整个任务得分 0.0
- 如果技能未被触发: 此项得分 1.0

### 2. 合理响应 (40%)
- 即使不触发技能，代理是否给出了适当的响应？
- 用户的实际问题是否得到了回答或正确重定向？

## 评分指南
- **1.0**: 正确 - 技能未触发，给出了适当的响应
- **0.7-0.9**: 正确未触发但响应可以更好
- **0.4-0.6**: 正确未触发但响应较差
- **0.0-0.3**: 错误 - 技能被错误触发（假阳性）
"""
        return rubric

    def _slugify(self, text: str) -> str:
        """Convert text to slug format."""
        slug = re.sub(r"[^\w\s-]", "", text.lower())
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        return slug.strip("-")

    def _generate_expected(
        self,
        analysis: SkillAnalysis,
        case: TestCase,
        original_example: SkillExample | None = None,
    ) -> str:
        """Generate expected result for a test case.

        Args:
            analysis: Skill analysis result
            case: Test case to generate expected for
            original_example: Original example (for evolved cases)

        Returns:
            Expected result string
        """
        if not case.expected_trigger:
            # 负向问题：期望不触发技能
            return "问题与本技能无关，SKILL.md 不应被读取"

        # 正向问题：根据来源生成期望
        if case.source == "原始-技能提供":
            # 从 SKILL.md 的示例中提取答案（优先使用现成答案）
            for example in analysis.examples:
                if example.input == case.instruction and example.expected_output:
                    return example.expected_output
            # 如果没有现成答案，用 LLM + 完整 SKILL.md 生成
            return self._llm_generate_expected(analysis, case)

        elif case.source == "演化":
            # 演化问题：基于原问题答案 + 完整 SKILL.md 生成
            if original_example and original_example.expected_output:
                return self._llm_evolve_expected(analysis, case, original_example)
            # 无原答案参考，直接用 LLM 生成
            return self._llm_generate_expected(analysis, case)

        else:  # LLM生成
            # 完全由 LLM + 完整 SKILL.md 生成
            return self._llm_generate_expected(analysis, case)

    def _llm_generate_expected(self, analysis: SkillAnalysis, case_or_instruction: TestCase | str) -> str:
        """Use LLM to generate expected result using complete SKILL.md content.

        Args:
            analysis: Skill analysis
            case_or_instruction: Test case or instruction string

        Returns:
            Expected result string
        """
        client = self._get_llm_client()
        if not client:
            return self._simple_expected(analysis, case_or_instruction)

        # 支持传入 TestCase 或字符串
        if isinstance(case_or_instruction, TestCase):
            instruction = case_or_instruction.instruction
        else:
            instruction = case_or_instruction

        # 使用完整的 SKILL.md 内容，而不仅仅是描述
        prompt = f"""你是一个技能执行模拟器。请基于以下完整的技能定义，模拟执行用户请求并生成期望的输出结果。

# 完整技能定义 (SKILL.md)

{self._skill_md_content}

---

# 用户请求

{instruction}

---

# 任务

请模拟执行上述用户请求，生成一个**准确、完整**的期望输出。

## 要求

1. **严格遵循技能定义**：输出必须符合技能描述的所有要求
2. **格式正确**：按照技能定义的输出格式生成
3. **内容准确**：包含所有必要信息，数值计算要准确
4. **语言一致**：使用中文回复

## 输出格式

直接输出期望结果，不要解释或添加额外内容。
"""

        try:
            response = client.chat.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            return content.strip()
        except Exception as e:
            print(f"Warning: LLM expected generation failed: {e}")
            return self._simple_expected(analysis, case_or_instruction)

    def _llm_evolve_expected(
        self,
        analysis: SkillAnalysis,
        case: TestCase,
        original_example: SkillExample,
    ) -> str:
        """Use LLM to evolve expected result based on original.

        Args:
            analysis: Skill analysis
            case: Evolved test case
            original_example: Original example with expected output

        Returns:
            Expected result string
        """
        client = self._get_llm_client()
        if not client:
            return self._simple_expected(analysis, case)

        prompt = f"""你是一个技能执行模拟器。请基于以下完整的技能定义，模拟执行用户请求并生成期望的输出结果。

# 完整技能定义 (SKILL.md)

{self._skill_md_content}

---

# 原始示例（供参考）

原始用户请求: {original_example.input}
原始期望输出: {original_example.expected_output}

---

# 新的用户请求（演化版本）

{case.instruction}

---

# 任务

请参考原始示例的输出风格和格式，为新请求生成**准确、完整**的期望输出。

## 要求

1. 保持与原始输出相似的风格和格式
2. 根据新请求的具体参数调整内容
3. 严格遵循技能定义

## 输出格式

直接输出期望结果，不要解释。
"""

        try:
            response = client.chat.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            return content.strip()
        except Exception as e:
            print(f"Warning: LLM evolve expected failed: {e}")
            return self._simple_expected(analysis, case)

    def _simple_expected(self, analysis: SkillAnalysis, case_or_instruction: TestCase | str) -> str:
        """Simple fallback expected generation without LLM."""
        if isinstance(case_or_instruction, TestCase):
            if case_or_instruction.expected_trigger:
                return f"[期望] 技能 '{analysis.metadata.name}' 被正确触发并执行"
            else:
                return "问题与本技能无关，SKILL.md 不应被读取"
        else:
            # 字符串参数，假设是正向用例
            return f"[期望] 技能 '{analysis.metadata.name}' 被正确触发并执行"

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


def generate_eval_plan(skill_dir: Path, model: str | None = None) -> EvalConfig:
    """Generate evaluation plan using three-layer test case strategy.

    Args:
        skill_dir: Path to the skill directory
        model: Optional model name for generation

    Returns:
        EvalConfig with three-layer test cases
    """
    generator = EvalPlanGenerator(model=model)
    return generator.generate(skill_dir)
