"""Static analyzer for SKILL.md - checks completeness and correctness without running Agent."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class StaticCheckResult:
    """Result of a single static check."""

    name: str
    passed: bool
    severity: str  # error, warning, info
    message: str
    details: str | None = None


@dataclass
class StaticAnalysisReport:
    """Complete static analysis report for a skill."""

    skill_name: str
    skill_path: Path
    checks: list[StaticCheckResult] = field(default_factory=list)

    # Scores
    function_completeness: float = 0.0  # 功能完整度
    reference_integrity: float = 0.0    # 引用完整性
    correctness: float = 0.0            # 正确性
    edge_case_coverage: float = 0.0     # 边界处理
    format_compliance: float = 0.0      # 格式规范

    @property
    def overall_score(self) -> float:
        """Calculate weighted overall score."""
        return (
            self.function_completeness * 0.30 +
            self.reference_integrity * 0.25 +
            self.correctness * 0.20 +
            self.edge_case_coverage * 0.15 +
            self.format_compliance * 0.10
        )

    @property
    def errors(self) -> list[StaticCheckResult]:
        """Get all error-level checks."""
        return [c for c in self.checks if c.severity == "error"]

    @property
    def warnings(self) -> list[StaticCheckResult]:
        """Get all warning-level checks."""
        return [c for c in self.checks if c.severity == "warning"]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "skillName": self.skill_name,
            "skillPath": str(self.skill_path),
            "overallScore": round(self.overall_score, 2),
            "scores": {
                "functionCompleteness": round(self.function_completeness, 2),
                "referenceIntegrity": round(self.reference_integrity, 2),
                "correctness": round(self.correctness, 2),
                "edgeCaseCoverage": round(self.edge_case_coverage, 2),
                "formatCompliance": round(self.format_compliance, 2),
            },
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "severity": c.severity,
                    "message": c.message,
                    "details": c.details,
                }
                for c in self.checks
            ],
            "summary": {
                "totalChecks": len(self.checks),
                "passed": sum(1 for c in self.checks if c.passed),
                "errors": len(self.errors),
                "warnings": len(self.warnings),
            },
        }


class StaticAnalyzer:
    """Static analyzer for SKILL.md files.

    Performs static analysis without running the Agent:
    - Checks SKILL.md structure completeness
    - Validates referenced files/directories exist
    - Checks description correctness
    - Evaluates edge case coverage
    - Validates format compliance
    """

    # Required sections for a complete SKILL.md
    REQUIRED_SECTIONS = [
        ("何时使用", ["when to use", "usage", "use cases"]),
        ("核心功能", ["core functions", "functions", "features"]),
        ("输出格式", ["output format", "output", "format"]),
    ]

    # Recommended sections
    RECOMMENDED_SECTIONS = [
        ("示例", ["examples", "example"]),
        ("错误处理", ["error handling", "errors", "error"]),
        ("安全注意", ["security", "security notes", "注意事项"]),
        ("工作流程", ["workflow", "process", "steps"]),
        ("验证规则", ["validation", "rules", "验证"]),
    ]

    def __init__(self):
        """Initialize the static analyzer."""
        pass

    def analyze(self, skill_dir: Path) -> StaticAnalysisReport:
        """Perform static analysis on a skill directory.

        Args:
            skill_dir: Path to the skill directory (contains SKILL.md)

        Returns:
            StaticAnalysisReport with all check results
        """
        skill_dir = skill_dir.resolve()
        skill_md = skill_dir / "SKILL.md"

        report = StaticAnalysisReport(
            skill_name=skill_dir.name,
            skill_path=skill_dir,
        )

        if not skill_md.exists():
            report.checks.append(StaticCheckResult(
                name="SKILL.md 存在性",
                passed=False,
                severity="error",
                message=f"SKILL.md not found in {skill_dir}",
            ))
            return report

        content = skill_md.read_text(encoding="utf-8")

        # 1. Check frontmatter
        self._check_frontmatter(content, report)

        # 2. Check required sections
        self._check_sections(content, report)

        # 3. Check referenced files
        self._check_references(skill_dir, content, report)

        # 4. Check examples
        self._check_examples(content, report)

        # 5. Calculate scores
        self._calculate_scores(report)

        return report

    def _check_frontmatter(self, content: str, report: StaticAnalysisReport) -> None:
        """Check YAML frontmatter completeness."""
        import yaml

        # Check frontmatter exists
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if not match:
            report.checks.append(StaticCheckResult(
                name="Frontmatter 存在性",
                passed=False,
                severity="error",
                message="SKILL.md must start with YAML frontmatter (---)",
            ))
            return

        report.checks.append(StaticCheckResult(
            name="Frontmatter 存在性",
            passed=True,
            severity="info",
            message="YAML frontmatter found",
        ))

        # Parse frontmatter
        try:
            frontmatter = yaml.safe_load(match.group(1))
        except yaml.YAMLError as e:
            report.checks.append(StaticCheckResult(
                name="Frontmatter 语法",
                passed=False,
                severity="error",
                message=f"Invalid YAML in frontmatter: {e}",
            ))
            return

        # Check required fields
        required_fields = ["name", "description"]
        for field in required_fields:
            if field not in frontmatter or not frontmatter[field]:
                report.checks.append(StaticCheckResult(
                    name=f"Frontmatter.{field}",
                    passed=False,
                    severity="error",
                    message=f"Required field '{field}' is missing or empty",
                ))
            else:
                report.checks.append(StaticCheckResult(
                    name=f"Frontmatter.{field}",
                    passed=True,
                    severity="info",
                    message=f"{field}: {str(frontmatter[field])[:50]}...",
                ))

        # Check description quality
        if "description" in frontmatter:
            desc = frontmatter["description"]
            if len(desc) < 20:
                report.checks.append(StaticCheckResult(
                    name="Description 质量",
                    passed=False,
                    severity="warning",
                    message="Description is too short (should be at least 20 characters)",
                ))
            elif len(desc) > 500:
                report.checks.append(StaticCheckResult(
                    name="Description 长度",
                    passed=False,
                    severity="warning",
                    message="Description is too long (should be under 500 characters)",
                ))
            else:
                report.checks.append(StaticCheckResult(
                    name="Description 质量",
                    passed=True,
                    severity="info",
                    message=f"Description length: {len(desc)} characters",
                ))

    def _check_sections(self, content: str, report: StaticAnalysisReport) -> None:
        """Check required and recommended sections."""
        # Extract all ## level headers
        sections = re.findall(r"^##\s+(.+)$", content, re.MULTILINE)
        section_lower = [s.lower() for s in sections]

        # Check required sections
        required_found = 0
        for cn_names, en_names in self.REQUIRED_SECTIONS:
            found = False
            for name in [cn_names] + en_names:
                if any(name.lower() in s for s in section_lower):
                    found = True
                    break

            if found:
                required_found += 1
                report.checks.append(StaticCheckResult(
                    name=f"必需章节: {cn_names}",
                    passed=True,
                    severity="info",
                    message=f"Section '{cn_names}' found",
                ))
            else:
                report.checks.append(StaticCheckResult(
                    name=f"必需章节: {cn_names}",
                    passed=False,
                    severity="error",
                    message=f"Required section '{cn_names}' not found",
                ))

        # Check recommended sections
        recommended_found = 0
        for cn_names, en_names in self.RECOMMENDED_SECTIONS:
            found = False
            for name in [cn_names] + en_names:
                if any(name.lower() in s for s in section_lower):
                    found = True
                    break

            if found:
                recommended_found += 1
                report.checks.append(StaticCheckResult(
                    name=f"推荐章节: {cn_names}",
                    passed=True,
                    severity="info",
                    message=f"Section '{cn_names}' found",
                ))
            else:
                report.checks.append(StaticCheckResult(
                    name=f"推荐章节: {cn_names}",
                    passed=False,
                    severity="warning",
                    message=f"Recommended section '{cn_names}' not found",
                ))

        # Calculate function completeness
        report.function_completeness = required_found / len(self.REQUIRED_SECTIONS)

    def _check_references(self, skill_dir: Path, content: str, report: StaticAnalysisReport) -> None:
        """Check if referenced files and directories exist."""
        referenced_files = []
        referenced_dirs = []

        # Find references in markdown links: [text](references/file.md)
        md_links = re.findall(r"\[.*?\]\((references|scripts|assets)/[^)]+\)", content)
        referenced_dirs.extend(md_links)

        # Find references in code blocks or text
        # e.g., "references/xxx.md", "scripts/xxx.py"
        file_refs = re.findall(r"(references|scripts|assets)/[\w\-./]+\.\w+", content)
        referenced_files.extend(file_refs)

        # Check directories
        dir_checks = {"references": 0, "scripts": 0, "assets": 0}
        for dir_name in ["references", "scripts", "assets"]:
            dir_path = skill_dir / dir_name
            if dir_path.exists() and dir_path.is_dir():
                files = list(dir_path.iterdir())
                if files:
                    dir_checks[dir_name] = 1
                    report.checks.append(StaticCheckResult(
                        name=f"目录: {dir_name}/",
                        passed=True,
                        severity="info",
                        message=f"Directory exists with {len(files)} files",
                        details=", ".join(f.name for f in files[:5]),
                    ))
                else:
                    report.checks.append(StaticCheckResult(
                        name=f"目录: {dir_name}/",
                        passed=False,
                        severity="warning",
                        message=f"Directory exists but is empty",
                    ))
            else:
                # Only warn if the directory is mentioned in SKILL.md
                if dir_name in content.lower():
                    report.checks.append(StaticCheckResult(
                        name=f"目录: {dir_name}/",
                        passed=False,
                        severity="warning",
                        message=f"Directory mentioned in SKILL.md but does not exist",
                    ))

        # Check individual file references
        file_checks_passed = 0
        file_checks_total = 0
        for file_ref in set(referenced_files):
            file_checks_total += 1
            file_path = skill_dir / file_ref
            if file_path.exists():
                file_checks_passed += 1
                report.checks.append(StaticCheckResult(
                    name=f"引用文件: {file_ref}",
                    passed=True,
                    severity="info",
                    message="File exists",
                ))
            else:
                report.checks.append(StaticCheckResult(
                    name=f"引用文件: {file_ref}",
                    passed=False,
                    severity="error",
                    message=f"Referenced file does not exist",
                ))

        # Calculate reference integrity
        if file_checks_total > 0:
            report.reference_integrity = file_checks_passed / file_checks_total
        else:
            # No files referenced, check if directories exist
            report.reference_integrity = sum(dir_checks.values()) / 3 if any(dir_checks.values()) else 1.0

    def _check_examples(self, content: str, report: StaticAnalysisReport) -> None:
        """Check examples section for completeness."""
        # Find examples section
        example_match = re.search(
            r"^##\s*(?:示例|Examples?).*?\n(.*?)(?=^##|\Z)",
            content,
            re.MULTILINE | re.DOTALL
        )

        if not example_match:
            report.checks.append(StaticCheckResult(
                name="示例章节存在性",
                passed=False,
                severity="warning",
                message="No examples section found",
            ))
            report.correctness = 0.5
            return

        examples_content = example_match.group(1)

        # Count examples (### headers or "示例" patterns)
        example_count = len(re.findall(r"^###\s+", examples_content, re.MULTILINE))
        if example_count == 0:
            example_count = len(re.findall(r"示例\s*\d+", examples_content))

        if example_count == 0:
            report.checks.append(StaticCheckResult(
                name="示例数量",
                passed=False,
                severity="warning",
                message="Examples section exists but no examples found",
            ))
        elif example_count < 2:
            report.checks.append(StaticCheckResult(
                name="示例数量",
                passed=False,
                severity="warning",
                message=f"Only {example_count} example(s) found, recommend at least 2",
            ))
        else:
            report.checks.append(StaticCheckResult(
                name="示例数量",
                passed=True,
                severity="info",
                message=f"Found {example_count} examples",
            ))

        # Check if examples have input/output
        has_input = bool(re.search(r"用户输入|Input|输入[：:]", examples_content, re.IGNORECASE))
        has_output = bool(re.search(r"技能输出|Output|输出[：:]", examples_content, re.IGNORECASE))

        if has_input:
            report.checks.append(StaticCheckResult(
                name="示例输入",
                passed=True,
                severity="info",
                message="Examples include input descriptions",
            ))
        else:
            report.checks.append(StaticCheckResult(
                name="示例输入",
                passed=False,
                severity="warning",
                message="Examples should include input descriptions",
            ))

        if has_output:
            report.checks.append(StaticCheckResult(
                name="示例输出",
                passed=True,
                severity="info",
                message="Examples include expected output",
            ))
        else:
            report.checks.append(StaticCheckResult(
                name="示例输出",
                passed=False,
                severity="warning",
                message="Examples should include expected output",
            ))

        # Calculate correctness based on example quality
        input_score = 1.0 if has_input else 0.5
        output_score = 1.0 if has_output else 0.5
        count_score = min(example_count / 2, 1.0) if example_count > 0 else 0.0
        report.correctness = (input_score + output_score + count_score) / 3

    def _calculate_scores(self, report: StaticAnalysisReport) -> None:
        """Calculate final scores based on check results."""
        # Edge case coverage - check if error handling section exists
        has_error_section = any(
            c.name.startswith("推荐章节: 错误处理") and c.passed
            for c in report.checks
        )
        has_security_section = any(
            c.name.startswith("推荐章节: 安全注意") and c.passed
            for c in report.checks
        )

        edge_score = 0.0
        if has_error_section:
            edge_score += 0.5
        if has_security_section:
            edge_score += 0.5
        report.edge_case_coverage = edge_score

        # Format compliance - check frontmatter and structure
        format_checks = [
            c for c in report.checks
            if "Frontmatter" in c.name
        ]
        if format_checks:
            report.format_compliance = sum(1 for c in format_checks if c.passed) / len(format_checks)
        else:
            report.format_compliance = 0.0


def run_static_analysis(skill_dir: Path) -> StaticAnalysisReport:
    """Run static analysis on a skill directory.

    Args:
        skill_dir: Path to the skill directory

    Returns:
        StaticAnalysisReport with all check results
    """
    analyzer = StaticAnalyzer()
    return analyzer.analyze(skill_dir)


def format_static_report(report: StaticAnalysisReport) -> str:
    """Format static analysis report for CLI output.

    Args:
        report: Static analysis report

    Returns:
        Formatted string for CLI output
    """
    lines = []
    lines.append(f"\nStatic Analysis Report for {report.skill_name}")
    lines.append("=" * (28 + len(report.skill_name)))
    lines.append("")

    # Summary
    lines.append(f"Overall Score: {report.overall_score:.2f}/1.00")
    lines.append("")
    lines.append("Score Breakdown:")
    lines.append(f"  Function Completeness:  {report.function_completeness:.2f}")
    lines.append(f"  Reference Integrity:    {report.reference_integrity:.2f}")
    lines.append(f"  Correctness:            {report.correctness:.2f}")
    lines.append(f"  Edge Case Coverage:     {report.edge_case_coverage:.2f}")
    lines.append(f"  Format Compliance:      {report.format_compliance:.2f}")
    lines.append("")

    # Checks
    if report.errors:
        lines.append("Errors:")
        for check in report.errors:
            lines.append(f"  ✗ {check.name}: {check.message}")
        lines.append("")

    if report.warnings:
        lines.append("Warnings:")
        for check in report.warnings:
            lines.append(f"  ⚠ {check.name}: {check.message}")
        lines.append("")

    passed_checks = [c for c in report.checks if c.passed and c.severity == "info"]
    if passed_checks:
        lines.append("Passed Checks:")
        for check in passed_checks[:10]:  # Limit output
            lines.append(f"  ✓ {check.name}")
        if len(passed_checks) > 10:
            lines.append(f"  ... and {len(passed_checks) - 10} more")
        lines.append("")

    # Summary
    lines.append(f"Total: {sum(1 for c in report.checks if c.passed)}/{len(report.checks)} checks passed")

    return "\n".join(lines)
