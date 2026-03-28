"""LLM-based boundary test case generator.

Generates boundary test cases by analyzing SKILL.md through LLM,
identifying boundary conditions such as:
1. Numeric boundaries (min/max values)
2. Input completeness (missing required fields)
3. Format boundaries (invalid formats, special characters)
4. Business-specific boundaries (from skill definition)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from rich.console import Console

from .context import SkillContext

console = Console()


@dataclass
class BoundaryTestCase:
    """A boundary test case."""

    name: str
    instruction: str
    expected_trigger: bool
    boundary_type: str  # 数值|完整性|格式|业务
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "instruction": self.instruction,
            "expectedTrigger": self.expected_trigger,
            "boundaryType": self.boundary_type,
            "description": self.description,
        }


class LLMBoundaryGenerator:
    """LLM-based boundary test case generator.

    Uses LLM to identify boundary conditions from skill definition
    and generate appropriate test cases.
    """

    PROMPT = """根据技能定义，生成边界测试用例。

## 技能定义
{skill_context}

## 任务
请识别该技能的边界条件，并为每个边界条件生成一个测试用例。

## 边界条件类型

1. **数值边界**: 最大值、最小值、零值、负值、超限值
2. **输入完整性**: 必填字段缺失、部分缺失、全部缺失
3. **格式边界**: 错误格式、特殊字符、超长输入、空值
4. **业务边界**: 该技能特有的边界场景（如大额转账、跨境交易等）

## 要求

1. 用户输入应该测试一个具体的边界条件
2. 使用自然语言，符合真实用户表达习惯
3. 每个用例只测试一个边界条件
4. 考虑技能定义中提到的验证规则、限制条件

## 输出格式 (仅JSON)
```json
{{
  "boundary_cases": [
    {{
      "name": "测试用例名称",
      "instruction": "用户输入",
      "expected_trigger": true或false,
      "boundary_type": "数值|完整性|格式|业务",
      "description": "测试的边界条件说明"
    }}
  ]
}}
```

请生成 {num_cases} 个边界测试用例。只输出JSON，不要其他内容。"""

    def __init__(self, llm_client: Any = None):
        """Initialize the generator.

        Args:
            llm_client: LLM client for generation
        """
        self.llm_client = llm_client
        self._skill_context: SkillContext | None = None

    def set_skill_context(self, context: SkillContext) -> None:
        """Set skill context for generation.

        Args:
            context: SkillContext extracted from SKILL.md
        """
        self._skill_context = context

    def get_skill_context(self) -> SkillContext | None:
        """Get current skill context."""
        return self._skill_context

    def generate(self, num_cases: int = 3) -> list[BoundaryTestCase]:
        """Generate boundary test cases.

        Args:
            num_cases: Number of boundary cases to generate

        Returns:
            List of BoundaryTestCase
        """
        if not self.llm_client or not self._skill_context:
            return []

        prompt = self.PROMPT.format(
            skill_context=self._skill_context.to_prompt_text(),
            num_cases=num_cases,
        )

        try:
            response = self.llm_client.chat.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            return self._parse_response(content)
        except Exception as e:
            console.print(f"[yellow]Warning: Boundary case generation failed: {e}[/yellow]")
            return []

    def _parse_response(self, content: str) -> list[BoundaryTestCase]:
        """Parse LLM response to list of BoundaryTestCase."""
        match = re.search(r'\{[\s\S]*\}', content)
        if not match:
            return []

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return []

        cases = []
        for bc in data.get("boundary_cases", []):
            instruction = bc.get("instruction", "")
            if not instruction:
                continue

            cases.append(BoundaryTestCase(
                name=bc.get("name", "边界测试"),
                instruction=instruction,
                expected_trigger=bc.get("expected_trigger", True),
                boundary_type=bc.get("boundary_type", "业务"),
                description=bc.get("description", ""),
            ))

        return cases

    def generate_as_dicts(self, num_cases: int = 3) -> list[dict[str, Any]]:
        """Generate boundary test cases as dictionaries.

        Args:
            num_cases: Number of boundary cases to generate

        Returns:
            List of dicts suitable for TestCase creation
        """
        cases = self.generate(num_cases)
        return [
            {
                "name": case.name,
                "instruction": case.instruction,
                "expected_trigger": case.expected_trigger,
                "source": f"边界测试-{case.boundary_type}",
            }
            for case in cases
        ]
