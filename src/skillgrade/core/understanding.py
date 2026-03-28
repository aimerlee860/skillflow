"""Skill understanding analyzer - analyzes skill complexity and characteristics.

This module provides LLM-based analysis of skill definitions to:
1. Assess complexity level (simple/moderate/complex)
2. Identify core functions and their importance
3. Determine applicable boundary condition types
4. Recommend test strategy (count, type weights)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console

from ..types import ComplexityLevel, DifficultyLevel, FunctionSpec, SkillProfile
from .context import SkillContext, SkillContextExtractor

console = Console()


class SkillUnderstandingAnalyzer:
    """LLM-based skill understanding analyzer.

    Analyzes SKILL.md to extract:
    - Complexity assessment
    - Core functions
    - Boundary types
    - Test strategy recommendations
    """

    SUMMARY_PROMPT = """请仔细阅读技能的所有文件，输出技能的摘要，字数多于500，少于600，要求尽量保留细节。

## 技能定义

{skill_context}

## 要求

1. 摘要应涵盖技能的核心功能、使用场景、工作流程、验证规则等关键信息
2. 保留重要细节，如参数要求、边界条件、输出格式等
3. 结构清晰，语言简洁
4. 字数控制在 500-600 字之间

只输出摘要内容，不要其他内容。"""

    ANALYSIS_PROMPT = """你是技能分析专家。请分析以下技能定义，提取测试规划所需的信息。

## 技能定义

{skill_context}

## 分析任务

请从以下维度进行量化分析:

### 1. 复杂度评估 (每项 1-10 分)

- **步骤复杂度** (step_complexity): 工作流程有多少步骤? 简单的1-3步=1-3分, 中等4-6步=4-6分, 复杂7+步=7-10分
- **参数复杂度** (param_complexity): 需要多少输入参数/字段? 少量1-2个=1-3分, 中等3-5个=4-6分, 很多6+个=7-10分
- **验证复杂度** (validation_complexity): 有多少验证规则/边界条件? 少=1-3分, 中=4-6分, 多=7-10分
- **推理复杂度** (reasoning_complexity): 需要多深层的推理? 简单匹配=1-3分, 需要组合=4-6分, 需要深层推理=7-10分

### 2. 核心功能列表

列出该技能的 3-8 个核心功能点，每个功能包含:
- name: 功能名称 (简短)
- weight: 重要性权重 (0.0-1.0, 所有权重之和建议约等于1.0)
- input_fields: 相关的输入字段列表

### 3. 边界条件类型

识别适用的边界类型 (从以下选项中选择):
- numeric: 数值边界 (最大/最小/零值/负值/超限)
- completeness: 完整性边界 (必填字段缺失/部分缺失)
- format: 格式边界 (错误格式/特殊字符/超长输入)
- business: 业务边界 (该技能特有的业务规则边界)

### 4. 测试策略建议

- **recommended_total**: 建议的总测试用例数量 (综合考虑复杂度，建议 6-20)
- **type_weights**: 各类型测试的推荐权重 (positive, negative, evolved, boundary，总和为1.0)

## 输出格式 (仅JSON)

```json
{{
  "complexity_factors": {{
    "step_complexity": 1-10,
    "param_complexity": 1-10,
    "validation_complexity": 1-10,
    "reasoning_complexity": 1-10
  }},
  "core_functions": [
    {{
      "name": "功能名称",
      "weight": 0.0-1.0,
      "input_fields": ["字段1", "字段2"]
    }}
  ],
  "boundary_types": ["numeric", "completeness", ...],
  "test_strategy": {{
    "recommended_total": 10,
    "type_weights": {{
      "positive": 0.40,
      "negative": 0.20,
      "evolved": 0.20,
      "boundary": 0.20
    }}
  }}
}}
```

只输出JSON，不要其他内容。"""

    def __init__(self, llm_client: Any = None, model: str | None = None):
        """Initialize the analyzer.

        Args:
            llm_client: LLM client for analysis
            model: Model name (for logging purposes)
        """
        self.llm_client = llm_client
        self.model = model
        self._skill_context: SkillContext | None = None

    def _get_llm_client(self):
        """Get or create LLM client."""
        if self.llm_client is None:
            try:
                from ..llm.client import get_llm_client
                self.llm_client = get_llm_client(model_name=self.model)
            except Exception:
                return None
        return self.llm_client

    def analyze(self, skill_dir: Path) -> SkillProfile:
        """Analyze skill definition and return profile.

        Args:
            skill_dir: Path to skill directory (must contain SKILL.md)

        Returns:
            SkillProfile with complexity, functions, and recommendations
        """
        skill_md_path = skill_dir / "SKILL.md"
        if not skill_md_path.exists():
            return self._default_profile()

        # Extract skill context
        context_extractor = SkillContextExtractor()
        self._skill_context = context_extractor.extract(skill_md_path)

        # Try LLM analysis
        llm_client = self._get_llm_client()
        if llm_client:
            try:
                return self._llm_analyze()
            except Exception as e:
                console.print(f"[yellow]Warning: LLM analysis failed: {e}, using rule-based fallback[/yellow]")

        # Fallback to rule-based analysis
        return self._rule_based_analyze(skill_dir)

    def _llm_analyze(self) -> SkillProfile:
        """Use LLM to analyze skill complexity."""
        if not self._skill_context:
            return self._default_profile()

        prompt = self.ANALYSIS_PROMPT.format(
            skill_context=self._skill_context.to_full_context()
        )

        response = self.llm_client.chat.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        profile = self._parse_response(content)

        # Generate skill summary (500-600 characters)
        summary = self._generate_summary()
        profile.summary = summary

        return profile

    def _generate_summary(self) -> str | None:
        """Generate skill summary using LLM (500-600 characters)."""
        if not self._skill_context:
            return None

        prompt = self.SUMMARY_PROMPT.format(
            skill_context=self._skill_context.to_full_context()
        )

        try:
            response = self.llm_client.chat.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            return content.strip()
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to generate skill summary: {e}[/yellow]")
            return None

    def _parse_response(self, content: str) -> SkillProfile:
        """Parse LLM response to SkillProfile."""
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return self._default_profile()

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return self._default_profile()

        # Extract complexity factors
        factors = data.get("complexity_factors", {})
        avg_score = sum(factors.values()) / len(factors) if factors else 5.0

        # Determine complexity level
        if avg_score <= 3.5:
            complexity = ComplexityLevel.SIMPLE
        elif avg_score <= 6.5:
            complexity = ComplexityLevel.MODERATE
        else:
            complexity = ComplexityLevel.COMPLEX

        # Extract core functions
        core_functions = []
        for func in data.get("core_functions", []):
            core_functions.append(FunctionSpec(
                name=func.get("name", "unknown"),
                weight=float(func.get("weight", 1.0)),
                input_fields=func.get("input_fields", []),
            ))

        # Normalize function weights if needed
        if core_functions:
            total_weight = sum(f.weight for f in core_functions)
            if total_weight > 0 and abs(total_weight - 1.0) > 0.1:
                for f in core_functions:
                    f.weight = f.weight / total_weight

        # Extract boundary types
        boundary_types = data.get("boundary_types", [])

        # Extract test strategy
        strategy = data.get("test_strategy", {})
        recommended_total = strategy.get("recommended_total", 10)
        type_weights = strategy.get("type_weights", {
            "positive": 0.4,
            "negative": 0.2,
            "evolved": 0.2,
            "boundary": 0.2,
        })

        return SkillProfile(
            complexity=complexity,
            complexity_factors=factors,
            core_functions=core_functions,
            boundary_types=boundary_types,
            recommended_total=recommended_total,
            type_weights=type_weights,
        )

    def _rule_based_analyze(self, skill_dir: Path) -> SkillProfile:
        """Fallback rule-based analysis when LLM is unavailable."""
        skill_md_path = skill_dir / "SKILL.md"
        content = skill_md_path.read_text(encoding="utf-8")

        # Count various complexity indicators
        step_count = len(re.findall(r"^\s*[-*]\s+", content, re.MULTILINE))
        heading_count = len(re.findall(r"^#{2,4}\s+", content, re.MULTILINE))
        field_count = len(re.findall(r"\*\*.*?\*\*:", content))
        rule_count = len(re.findall(r"(?:验证|规则|限制|必须|不能)", content))

        # Calculate complexity factors
        factors = {
            "step_complexity": min(10, step_count // 2 + 1),
            "param_complexity": min(10, field_count // 2 + 1),
            "validation_complexity": min(10, rule_count // 2 + 1),
            "reasoning_complexity": min(10, heading_count // 2 + 1),
        }

        avg_score = sum(factors.values()) / len(factors)

        if avg_score <= 3.5:
            complexity = ComplexityLevel.SIMPLE
            recommended_total = 6
        elif avg_score <= 6.5:
            complexity = ComplexityLevel.MODERATE
            recommended_total = 10
        else:
            complexity = ComplexityLevel.COMPLEX
            recommended_total = 16

        return SkillProfile(
            complexity=complexity,
            complexity_factors=factors,
            core_functions=[
                FunctionSpec(name="核心功能", weight=1.0, input_fields=[])
            ],
            boundary_types=["completeness", "format"],
            recommended_total=recommended_total,
            type_weights={
                "positive": 0.4,
                "negative": 0.2,
                "evolved": 0.2,
                "boundary": 0.2,
            },
        )

    def _default_profile(self) -> SkillProfile:
        """Return default profile when analysis fails."""
        return SkillProfile(
            complexity=ComplexityLevel.MODERATE,
            complexity_factors={
                "step_complexity": 5.0,
                "param_complexity": 5.0,
                "validation_complexity": 5.0,
                "reasoning_complexity": 5.0,
            },
            core_functions=[
                FunctionSpec(name="默认功能", weight=1.0, input_fields=[])
            ],
            boundary_types=["completeness"],
            recommended_total=10,
            type_weights={
                "positive": 0.4,
                "negative": 0.2,
                "evolved": 0.2,
                "boundary": 0.2,
            },
        )
