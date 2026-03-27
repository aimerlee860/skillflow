"""Skill tracking statistics calculator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union

from ..types import SkillTrackingReport


@dataclass
class SkillStatistics:
    """Calculated statistics for skill usage."""

    skill_name: str
    trigger_accuracy: float
    deep_usage_accuracy: float
    false_positive_rate: float
    shallow_usage_rate: float
    avg_time_to_first_access: float
    avg_access_count_per_trial: float
    effective_usage_rate: float
    # Quality score components
    task_completion_score: float  # Task success rate
    efficiency_score: float  # Higher for less resource usage
    quality_score: float  # Composite score

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "skillName": self.skill_name,
            "triggerAccuracy": self.trigger_accuracy,
            "deepUsageAccuracy": self.deep_usage_accuracy,
            "falsePositiveRate": self.false_positive_rate,
            "shallowUsageRate": self.shallow_usage_rate,
            "avgTimeToFirstAccess": self.avg_time_to_first_access,
            "avgAccessCountPerTrial": self.avg_access_count_per_trial,
            "effectiveUsageRate": self.effective_usage_rate,
            "taskCompletionScore": self.task_completion_score,
            "efficiencyScore": self.efficiency_score,
            "qualityScore": self.quality_score,
        }


def calculate_skill_statistics(
    tracking_reports: list[Union[SkillTrackingReport, dict[str, Any]]],
    trial_results: list[dict[str, Any]],
) -> list[SkillStatistics]:
    """Calculate comprehensive skill statistics.

    Quality Evaluation Philosophy:
    ---------------------------------
    Skill quality is ONLY evaluated when the skill is actually accessed.
    "Injected but not accessed" does NOT indicate skill quality - it just means
    the model could handle the task without this skill.

    Quality Score Components (only for accessed trials):
    1. Task Completion Score (70%): When skill IS used, does it help succeed?
    2. Efficiency Score (30%): When skill IS used, is it efficient?
       - Shallow usage (SKILL.md only) = skill description is clear
       - Fewer file accesses = skill is well-organized

    Note: This evaluates SKILL QUALITY, not skill INJECTION accuracy.
    False positive rate (injection accuracy) is tracked separately.

    Args:
        tracking_reports: List of skill tracking reports (SkillTrackingReport or dict)
        trial_results: List of trial results with tracking data

    Returns:
        List of SkillStatistics for each skill
    """
    statistics = []

    for report in tracking_reports:
        # Handle both SkillTrackingReport objects and dicts
        if isinstance(report, SkillTrackingReport):
            skill_name = report.skill_name
            false_positive_rate = report.false_positive_rate
        else:
            skill_name = report["skillName"]
            false_positive_rate = report.get("falsePositiveRate", 0)

        # Gather per-trial data
        trials_with_skill = [
            t
            for t in trial_results
            if any(
                s["skillName"] == skill_name for s in t.get("skillTracking", [])
            )
        ]

        if not trials_with_skill:
            continue

        # Calculate metrics
        accessed_trials = [
            t
            for t in trials_with_skill
            if any(
                s["accessDepth"] >= 1
                for s in t.get("skillTracking", [])
                if s["skillName"] == skill_name
            )
        ]

        deep_usage_trials = [
            t
            for t in trials_with_skill
            if any(
                s["accessDepth"] >= 2
                for s in t.get("skillTracking", [])
                if s["skillName"] == skill_name
            )
        ]

        # Time to first access
        access_times = []
        for t in trials_with_skill:
            for s in t.get("skillTracking", []):
                if s["skillName"] == skill_name and s.get("firstAccessTime"):
                    access_times.append(s["firstAccessTime"])

        avg_time_to_first = sum(access_times) / len(access_times) if access_times else 0.0

        # Access count
        total_accesses = sum(
            sum(
                len(s.get("accessRecords", []))
                for s in t.get("skillTracking", [])
                if s["skillName"] == skill_name
            )
            for t in trials_with_skill
        )
        avg_access_count = (
            total_accesses / len(trials_with_skill) if trials_with_skill else 0
        )

        # Calculate rates
        trigger_accuracy = (
            len(accessed_trials) / len(trials_with_skill) if trials_with_skill else 0
        )
        deep_usage_accuracy = (
            len(deep_usage_trials) / len(accessed_trials) if accessed_trials else 0
        )
        shallow_rate = (
            (len(accessed_trials) - len(deep_usage_trials)) / len(accessed_trials)
            if accessed_trials
            else 0
        )
        effective_usage_rate = (
            len(deep_usage_trials) / len(trials_with_skill) if trials_with_skill else 0
        )

        # === QUALITY SCORE CALCULATION ===
        # Three-factor evaluation:
        # 1. Task Completion (when accessed): does skill help succeed?
        # 2. Efficiency (when accessed): is skill easy to use?
        # 3. False Positive Penalty: wasted injections hurt overall efficiency

        # 1. Task completion quality - only for trials where skill was accessed
        if accessed_trials:
            task_completion_score = sum(
                t.get("reward", 0) for t in accessed_trials
            ) / len(accessed_trials)
        else:
            # No trials accessed this skill - cannot evaluate task completion
            task_completion_score = 0.0

        # 2. Efficiency score - only meaningful when skill IS accessed
        if accessed_trials:
            # Shallow usage efficiency: reading only SKILL.md = skill description is clear
            shallow_efficiency = 1 - deep_usage_accuracy

            # Access count efficiency: fewer file reads = skill is well-organized
            access_efficiency = max(0, 1 - ((avg_access_count - 2) / 5))

            efficiency_score = (
                shallow_efficiency * 0.6
                + access_efficiency * 0.4
            )
        else:
            efficiency_score = 0.0

        # 3. False Positive Penalty - wasted injections
        # Formula: (1 - false_positive_rate) where FPR = not_accessed / injected
        # - FPR = 0% (always accessed) → penalty factor = 1.0 (no penalty)
        # - FPR = 50% (half wasted) → penalty factor = 0.5 (reduce score by half)
        # - FPR = 100% (never accessed) → penalty factor = 0.0 (zero quality)
        no_access_rate = (
            (len(trials_with_skill) - len(accessed_trials)) / len(trials_with_skill)
            if trials_with_skill else 0
        )
        trigger_precision = 1 - no_access_rate  # = accessed / injected

        # 4. Composite quality score with false positive penalty
        # Base score from task completion and efficiency (when accessed)
        if accessed_trials:
            base_score = (
                task_completion_score * 0.6  # Primary: does it help?
                + efficiency_score * 0.4      # Secondary: is it efficient?
            )
            # Apply penalty: wasted injections reduce overall utility
            quality_score = base_score * trigger_precision
        else:
            # Never accessed = pure false positive, maximum penalty
            quality_score = 0.0

        stats = SkillStatistics(
            skill_name=skill_name,
            trigger_accuracy=trigger_accuracy,
            deep_usage_accuracy=deep_usage_accuracy,
            false_positive_rate=false_positive_rate,
            shallow_usage_rate=shallow_rate,
            avg_time_to_first_access=avg_time_to_first,
            avg_access_count_per_trial=avg_access_count,
            effective_usage_rate=effective_usage_rate,
            task_completion_score=task_completion_score,
            efficiency_score=efficiency_score,
            quality_score=quality_score,
        )
        statistics.append(stats)

    return statistics


def format_statistics_report(statistics: list[SkillStatistics]) -> str:
    """Format skill statistics as a readable report.

    Args:
        statistics: List of SkillStatistics to format

    Returns:
        Formatted report string
    """
    lines = [
        "=" * 60,
        "Skill Quality Statistics Report",
        "=" * 60,
        "",
        "Note: Quality scores only evaluate trials where skill was ACCESSED.",
        "'Injected but not accessed' doesn't indicate skill quality -",
        "it just means the model could handle the task without this skill.",
    ]

    for stat in statistics:
        # Determine quality assessment status
        if stat.trigger_accuracy == 0:
            quality_status = "(Never accessed - cannot evaluate quality)"
        else:
            quality_status = ""

        lines.extend(
            [
                f"\nSkill: {stat.skill_name} {quality_status}",
                "-" * 50,
                f"  Quality Score:         {stat.quality_score:.2f}",
                f"    ├── Task Completion: {stat.task_completion_score:.2%} (70%)",
                f"    └── Efficiency:      {stat.efficiency_score:.2%} (30%)",
                "",
                "  Access Patterns:",
                f"    Trigger Rate:        {stat.trigger_accuracy:.2%}",
                f"    Deep Usage Rate:     {stat.deep_usage_accuracy:.2%}",
                f"    Avg Accesses/Trial:  {stat.avg_access_count_per_trial:.1f}",
                "",
                "  Injection Accuracy:",
                f"    False Positive Rate: {stat.false_positive_rate:.2%}",
            ]
        )

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def format_tracking_summary(sessions: list[dict[str, Any]]) -> str:
    """Format skill tracking sessions as a brief summary.

    Args:
        sessions: List of skill tracking session dicts

    Returns:
        Formatted summary string
    """
    if not sessions:
        return "No skill tracking data"

    lines = ["Skill Access Summary:"]

    for session in sessions:
        skill_name = session.get("skillName", "unknown")
        depth = session.get("accessDepth", 0)
        records = session.get("accessRecords", [])

        depth_label = {0: "not accessed", 1: "SKILL.md only", 2: "deep usage"}.get(
            depth, f"depth {depth}"
        )

        lines.append(f"  - {skill_name}: {depth_label} ({len(records)} accesses)")

    return "\n".join(lines)
