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

from ..types import ComplexityLevel, DifficultyLevel, FunctionSpec, SkillAnalysis, SkillProfile
from .analysis import SkillAnalyzer
from .context import SkillContext, SkillContextExtractor
from prompts import PromptManager

console = Console()


class SkillUnderstandingAnalyzer:
    """LLM-based skill understanding analyzer.

    Analyzes SKILL.md to extract:
    - Complexity assessment
    - Core functions
    - Boundary types
    - Test strategy recommendations
    """


    def __init__(self, llm_client: Any = None, model: str | None = None):
        """Initialize the analyzer.

        Args:
            llm_client: LLM client for analysis
            model: Model name (for logging purposes)
        """
        self.llm_client = llm_client
        self.model = model
        self._skill_context: SkillContext | None = None
        self._structural_analysis: SkillAnalysis | None = None

    def _get_llm_client(self):
        """Get or create LLM client."""
        if self.llm_client is None:
            try:
                from ..llm.client import get_llm_client
                self.llm_client = get_llm_client(model_name=self.model)
            except Exception:
                return None
        return self.llm_client

    @property
    def structural_analysis(self) -> SkillAnalysis | None:
        """Return the structural analysis result from SkillAnalyzer."""
        return self._structural_analysis

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

        # Stage 1: Structural analysis (regex-based, fast, deterministic)
        try:
            structural_analyzer = SkillAnalyzer()
            self._structural_analysis = structural_analyzer.analyze(skill_dir)
        except Exception:
            self._structural_analysis = None

        # Stage 2: Extract skill context (full content)
        context_extractor = SkillContextExtractor()
        self._skill_context = context_extractor.extract(skill_md_path)

        # Stage 3: LLM analysis with structural context
        llm_client = self._get_llm_client()
        if llm_client:
            try:
                return self._llm_analyze()
            except Exception as e:
                console.print(f"[yellow]Warning: LLM analysis failed: {e}, using rule-based fallback[/yellow]")

        # Fallback to rule-based analysis (leveraging structural data)
        return self._rule_based_analyze()

    def _llm_analyze(self) -> SkillProfile:
        """Use LLM to analyze skill complexity with structural context.

        Two-pass approach with conditional revision:
        - Pass 1: Initial analysis → SkillProfile
        - Pass 2: Review + Summary → if issues found, trigger Pass 3
        - Pass 3 (conditional): Re-analysis with review feedback
        """
        if not self._skill_context:
            return self._default_profile()

        structural_context = self._build_structural_context()
        skill_content = self._skill_context.to_complete_context()

        # Pass 1: Initial analysis
        profile = self._pass1_initial_analysis(skill_content, structural_context)

        # Pass 2: Review + Summary
        review_result = self._pass2_review_and_summary(
            skill_content, structural_context, profile,
        )

        if review_result:
            profile.summary = review_result.get("summary")
            verdict = review_result.get("verdict", "pass")
            issues = review_result.get("issues", [])

            if verdict == "revise" and issues:
                console.print(f"[yellow]审核发现 {len(issues)} 个问题，重新分析...[/yellow]")
                for issue in issues:
                    console.print(f"  [dim]- {issue}[/dim]")

                # Pass 3: Re-analysis with review feedback
                revised = self._pass3_revised_analysis(
                    skill_content, structural_context, issues,
                )
                if revised:
                    profile = revised
                    # Re-generate summary for revised profile
                    review_result2 = self._pass2_review_and_summary(
                        skill_content, structural_context, profile,
                    )
                    if review_result2:
                        profile.summary = review_result2.get("summary")

        return profile

    def _pass1_initial_analysis(self, skill_content: str, structural_context: str) -> SkillProfile:
        """Pass 1: Initial LLM analysis of skill."""
        prompt = PromptManager.get(
            "skillgrade/skill_analysis",
            skill_context=skill_content,
            structural_context=structural_context,
        )

        response = self.llm_client.chat.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        return self._parse_response(content)

    def _pass2_review_and_summary(
        self,
        skill_content: str,
        structural_context: str,
        profile: SkillProfile,
    ) -> dict | None:
        """Pass 2: Review the analysis and generate summary.

        Returns dict with verdict, issues, and summary.
        """
        profile_text = json.dumps(profile.to_dict(), ensure_ascii=False, indent=2)

        prompt = PromptManager.get(
            "skillgrade/skill_review",
            skill_context=skill_content,
            structural_context=structural_context,
            initial_profile=profile_text,
        )

        try:
            response = self.llm_client.chat.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            return self._parse_review_response(content)
        except Exception as e:
            console.print(f"[yellow]Warning: Review pass failed: {e}[/yellow]")
            return None

    def _pass3_revised_analysis(
        self,
        skill_content: str,
        structural_context: str,
        issues: list[str],
    ) -> SkillProfile | None:
        """Pass 3: Re-analyze with review feedback incorporated into prompt."""
        feedback = "\n".join(f"- {issue}" for issue in issues)
        enhanced_structural = f"{structural_context}\n\n### 上次审核发现的问题\n{feedback}" if structural_context else f"### 上次审核发现的问题\n{feedback}"

        prompt = PromptManager.get(
            "skillgrade/skill_analysis",
            skill_context=skill_content,
            structural_context=enhanced_structural,
        )

        try:
            response = self.llm_client.chat.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            return self._parse_response(content)
        except Exception as e:
            console.print(f"[yellow]Warning: Revised analysis failed: {e}[/yellow]")
            return None

    def _parse_review_response(self, content: str) -> dict | None:
        """Parse review response JSON."""
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return None

        try:
            data = json.loads(match.group())
            if "verdict" not in data:
                return None
            return data
        except json.JSONDecodeError:
            return None

    def _build_structural_context(self) -> str:
        """Build structural context from SkillAnalyzer results for LLM prompt."""
        sa = self._structural_analysis
        if not sa:
            return ""

        parts = []

        if sa.workflows:
            parts.append("### 工作流程")
            for step in sorted(sa.workflows, key=lambda s: s.order):
                desc = f": {step.description}" if step.description else ""
                parts.append(f"- 步骤{step.order} {step.name}{desc}")

        if sa.examples:
            parts.append("\n### 已提取示例")
            for ex in sa.examples:
                parts.append(f"- **{ex.name}**")
                if ex.input:
                    parts.append(f"  输入: {ex.input[:200]}")
                if ex.expected_output:
                    parts.append(f"  输出: {ex.expected_output[:200]}")

        if sa.validation_rules:
            parts.append("\n### 验证规则")
            for rule in sa.validation_rules:
                parts.append(f"- {rule}")

        if sa.error_conditions:
            parts.append("\n### 错误处理条件")
            for err in sa.error_conditions:
                parts.append(f"- {err}")

        if sa.output_formats:
            parts.append("\n### 输出格式")
            for fmt in sa.output_formats:
                parts.append(f"- {fmt}")

        if sa.security_notes:
            parts.append("\n### 安全注意事项")
            for note in sa.security_notes:
                parts.append(f"- {note}")

        if sa.resources:
            parts.append("\n### 关联资源")
            for r in sa.resources:
                parts.append(f"- [{r.type}] {r.path} ({len(r.content)} chars)")

        return "\n".join(parts) if parts else ""

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
                description=func.get("description", ""),
                error_conditions=func.get("error_conditions", []),
                output_description=func.get("output_description", ""),
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
            user_scenarios=data.get("user_scenarios", []),
            function_dependencies=data.get("function_dependencies", []),
            domain_constraints=data.get("domain_constraints", []),
        )

    def _rule_based_analyze(self) -> SkillProfile:
        """Fallback rule-based analysis when LLM is unavailable.

        Uses structural analysis data for accurate assessment by considering
        both counts and content depth of each dimension.
        """
        sa = self._structural_analysis

        if not sa:
            return self._default_profile()

        # --- Complexity scoring: count + depth ---

        # Step complexity: workflow count + average description depth
        workflow_count = len(sa.workflows)
        if workflow_count:
            avg_step_depth = sum(len(s.description) for s in sa.workflows) / workflow_count
            # depth bonus: 0-3 points based on average description length
            depth_bonus = min(3, avg_step_depth / 80)
            step_complexity = min(10, workflow_count * 1.0 + depth_bonus + 1)
        else:
            step_complexity = 2.0

        # Param complexity: function count + use_cases breadth
        function_count = len(sa.core_functions)
        use_case_count = len(sa.use_cases)
        param_complexity = min(10, function_count * 1.2 + use_case_count * 0.5 + 1.5)

        # Validation complexity: rules + error conditions + rule detail
        rule_count = len(sa.validation_rules)
        error_count = len(sa.error_conditions)
        if rule_count or error_count:
            # Long rules imply more complex constraints
            avg_rule_len = (
                sum(len(r) for r in sa.validation_rules) / rule_count
                if rule_count else 0
            )
            rule_depth_bonus = min(2, avg_rule_len / 60)
            validation_complexity = min(10, rule_count * 0.8 + error_count * 0.6 + rule_depth_bonus + 1)
        else:
            validation_complexity = 2.0

        # Reasoning complexity: workflow depth + errors + security + output formats + resource activation
        security_count = len(sa.security_notes)
        output_format_count = len(sa.output_formats)
        example_count = len(sa.examples)

        # Resource activation signals
        resource_count = len(sa.resources)
        resource_types = {r.type for r in sa.resources}
        resource_volume = sum(len(r.content) for r in sa.resources)
        activation_signal = (
            resource_count * 0.6
            + (1.0 if "script" in resource_types else 0.0)
            + min(1.0, resource_volume / 5000)
        )

        reasoning_signals = (
            workflow_count * 0.5
            + error_count * 0.8
            + security_count * 1.0
            + output_format_count * 0.4
            + activation_signal
        )
        reasoning_complexity = min(10, reasoning_signals + 2.0)

        factors = {
            "step_complexity": round(step_complexity, 1),
            "param_complexity": round(param_complexity, 1),
            "validation_complexity": round(validation_complexity, 1),
            "reasoning_complexity": round(reasoning_complexity, 1),
        }

        avg_score = sum(factors.values()) / len(factors)

        if avg_score <= 3.5:
            complexity = ComplexityLevel.SIMPLE
            recommended_total = 4
        elif avg_score <= 6.5:
            complexity = ComplexityLevel.MODERATE
            recommended_total = 7
        else:
            complexity = ComplexityLevel.COMPLEX
            recommended_total = 12

        # --- Core functions from structural data ---
        core_functions = []
        if sa.core_functions:
            weight = round(1.0 / len(sa.core_functions[:8]), 2)
            for func_name in sa.core_functions[:8]:
                core_functions.append(FunctionSpec(
                    name=func_name,
                    weight=weight,
                    input_fields=[],
                ))
        else:
            core_functions = [FunctionSpec(name="核心功能", weight=1.0, input_fields=[])]

        # --- Boundary types: infer from actual content ---
        boundary_types = ["completeness"]
        all_text = " ".join(
            sa.validation_rules + sa.error_conditions + sa.security_notes
        ).lower()

        if any(kw in all_text for kw in ["数值", "数字", "数量", "金额", "长度", "大小", "范围", "上限", "下限", "numeric", "number"]):
            boundary_types.append("numeric")
        if sa.validation_rules or sa.output_formats:
            boundary_types.append("format")
        if sa.error_conditions or sa.security_notes:
            boundary_types.append("business")

        # --- Adjust test weights based on complexity profile ---
        if avg_score > 6.5:
            # Complex skills: more boundary and negative tests
            type_weights = {"positive": 0.30, "negative": 0.25, "evolved": 0.20, "boundary": 0.25}
        elif avg_score <= 3.5:
            # Simple skills: more positive tests
            type_weights = {"positive": 0.50, "negative": 0.15, "evolved": 0.20, "boundary": 0.15}
        else:
            type_weights = {"positive": 0.40, "negative": 0.20, "evolved": 0.20, "boundary": 0.20}

        return SkillProfile(
            complexity=complexity,
            complexity_factors=factors,
            core_functions=core_functions,
            boundary_types=boundary_types,
            recommended_total=recommended_total,
            type_weights=type_weights,
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
