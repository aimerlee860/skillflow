"""LLM-based difficulty assessment for test cases.

Assesses test case difficulty based on semantic understanding:
1. Information completeness - does input contain all required fields?
2. Expression clarity - is the user intent clear?
3. Intent clarity - does user know what they want?
4. Skill relevance - how well does it match the skill definition?

Key insight: Short inputs are NOT necessarily easy. Missing key information
is what makes a test case difficult.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ..types import DifficultyLevel
from .context import SkillContext


@dataclass
class DifficultyAssessment:
    """Result of difficulty assessment for a test case."""

    level: DifficultyLevel
    score: float  # 0.0-1.0

    # Assessment dimensions
    completeness: float = 0.5      # Information completeness (most important)
    clarity: float = 0.5           # Expression clarity
    intent_clarity: float = 0.5    # Intent clarity
    skill_relevance: float = 0.5   # Skill relevance

    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "level": self.level.value,
            "score": self.score,
            "completeness": self.completeness,
            "clarity": self.clarity,
            "intentClarity": self.intent_clarity,
            "skillRelevance": self.skill_relevance,
            "reasoning": self.reasoning,
        }


class LLMDifficultyAssessor:
    """LLM-based difficulty assessor for test cases.

    Uses LLM to understand semantic meaning of test cases and assess
    difficulty based on information completeness, not just text length.
    """

    PROMPT = """你是测试用例难度评估专家。根据技能定义评估测试用例难度。

## 技能定义
{skill_context}

## 测试用例
- 用户输入: {instruction}
- 期望触发: {expected_trigger}

## 评估维度

1. **信息完整性** (权重 40%): 输入是否包含执行技能所需的全部关键信息
   - 对照技能定义中的必填字段、验证规则
   - 关键信息缺失越多，难度越高

2. **表达清晰度** (权重 20%): 用户意图是否表达清晰无歧义
   - 是否有模糊表达（"可能"、"也许"、"大概"）
   - 是否有矛盾或冲突的信息

3. **意图明确度** (权重 20%): 用户是否清楚自己想要什么
   - 是否明确说明期望结果
   - 是否有条件或分支要求

4. **技能契合度** (权重 20%): 与技能定义的匹配程度
   - 是否属于该技能的核心使用场景
   - 是否需要额外的推理或判断

## 难度定义
- **easy** (0.0-0.35): 信息完整，可直接执行，无需追问
- **medium** (0.35-0.65): 部分信息缺失，需要简单推理或追问
- **hard** (0.65-1.0): 关键信息严重缺失，表达模糊，需要多轮交互

## 重要提示
- 短输入不一定难，长输入不一定简单
- 难度由信息完整性决定，不是文本长度
- "转账100元" 可能比 "转账100元给张三工行账号6222..." 更难（缺少收款人信息）

## 输出格式 (仅JSON)
```json
{{
  "completeness": 0.0-1.0,
  "clarity": 0.0-1.0,
  "intent_clarity": 0.0-1.0,
  "skill_relevance": 0.0-1.0,
  "overall_score": 0.0-1.0,
  "difficulty": "easy|medium|hard",
  "reasoning": "简要说明（为什么是这个难度）"
}}
```"""

    def __init__(self, llm_client: Any = None):
        """Initialize the assessor.

        Args:
            llm_client: LLM client for assessment
        """
        self.llm_client = llm_client
        self._skill_context: SkillContext | None = None

    def set_skill_context(self, context: SkillContext) -> None:
        """Set skill context for assessment.

        Args:
            context: SkillContext extracted from SKILL.md
        """
        self._skill_context = context

    def get_skill_context(self) -> SkillContext | None:
        """Get current skill context."""
        return self._skill_context

    def assess(
        self,
        instruction: str,
        expected_trigger: bool = True,
    ) -> DifficultyAssessment:
        """Assess difficulty of a test case.

        Args:
            instruction: User input instruction
            expected_trigger: Whether skill is expected to trigger

        Returns:
            DifficultyAssessment with level, score, and reasoning
        """
        if not self.llm_client or not self._skill_context:
            return self._default_assessment()

        prompt = self.PROMPT.format(
            skill_context=self._skill_context.to_prompt_text(),
            instruction=instruction,
            expected_trigger="是" if expected_trigger else "否",
        )

        try:
            response = self.llm_client.chat.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            return self._parse_response(content)
        except Exception as e:
            return self._default_assessment(error=str(e))

    def _parse_response(self, content: str) -> DifficultyAssessment:
        """Parse LLM response to DifficultyAssessment."""
        match = re.search(r'\{[\s\S]*\}', content)
        if not match:
            return self._default_assessment(error="No JSON found in response")

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return self._default_assessment(error="Invalid JSON in response")

        # Parse difficulty level
        level_map = {
            "easy": DifficultyLevel.EASY,
            "medium": DifficultyLevel.MEDIUM,
            "hard": DifficultyLevel.HARD,
        }
        level_str = data.get("difficulty", "medium").lower()
        level = level_map.get(level_str, DifficultyLevel.MEDIUM)

        return DifficultyAssessment(
            level=level,
            score=float(data.get("overall_score", 0.5)),
            completeness=float(data.get("completeness", 0.5)),
            clarity=float(data.get("clarity", 0.5)),
            intent_clarity=float(data.get("intent_clarity", 0.5)),
            skill_relevance=float(data.get("skill_relevance", 0.5)),
            reasoning=data.get("reasoning", ""),
        )

    def _default_assessment(self, error: str = "") -> DifficultyAssessment:
        """Return default assessment when LLM is unavailable."""
        return DifficultyAssessment(
            level=DifficultyLevel.MEDIUM,
            score=0.5,
            completeness=0.5,
            clarity=0.5,
            intent_clarity=0.5,
            skill_relevance=0.5,
            reasoning=f"LLM unavailable. {error}".strip(),
        )

    def batch_assess(
        self,
        cases: list[dict[str, Any]],
    ) -> list[DifficultyAssessment]:
        """Assess multiple test cases.

        Args:
            cases: List of dicts with 'instruction' and 'expected_trigger'

        Returns:
            List of DifficultyAssessment results
        """
        return [
            self.assess(
                instruction=case.get("instruction", ""),
                expected_trigger=case.get("expected_trigger", True),
            )
            for case in cases
        ]
