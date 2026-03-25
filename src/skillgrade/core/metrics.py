"""Metrics management module for skillgrade.

This module provides a unified way to manage and configure evaluation metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class MetricCategory(str, Enum):
    """Categories of metrics."""

    TASK = "task"  # Task-level evaluation metrics
    SKILL = "skill"  # Skill tracking metrics


class MetricType(str, Enum):
    """All supported metric types."""

    # Task evaluation metrics
    PASS_RATE = "pass_rate"
    PASS_AT_K = "pass_at_k"
    PASS_POW_K = "pass_pow_k"
    REWARD = "reward"

    # Skill tracking metrics
    ACCESS_RATE = "access_rate"
    DEEP_USAGE_RATE = "deep_usage_rate"
    FALSE_POSITIVE_RATE = "false_positive_rate"
    EFFECTIVE_USAGE_RATE = "effective_usage_rate"
    QUALITY_SCORE = "quality_score"
    TASK_COMPLETION_SCORE = "task_completion_score"
    EFFICIENCY_SCORE = "efficiency_score"


@dataclass
class MetricDefinition:
    """Definition of a metric."""

    name: str
    display_name: str
    category: MetricCategory
    description: str
    value_range: tuple[float, float] = (0.0, 1.0)
    higher_is_better: bool = True
    unit: str = ""
    format_pattern: str = ".2%"

    def format_value(self, value: float) -> str:
        """Format a metric value for display."""
        if self.format_pattern == ".2%":
            return f"{value:.2%}"
        elif self.format_pattern == ".4f":
            return f"{value:.4f}"
        elif self.format_pattern == ".2f":
            return f"{value:.2f}"
        return str(value)


# Predefined metric definitions
METRIC_DEFINITIONS: dict[MetricType, MetricDefinition] = {
    # Task evaluation metrics
    MetricType.PASS_RATE: MetricDefinition(
        name="pass_rate",
        display_name="Pass Rate",
        category=MetricCategory.TASK,
        description="Ratio of successful trials to total trials",
        value_range=(0.0, 1.0),
        higher_is_better=True,
        unit="%",
        format_pattern=".2%",
    ),
    MetricType.PASS_AT_K: MetricDefinition(
        name="pass_at_k",
        display_name="Pass@K",
        category=MetricCategory.TASK,
        description="Probability of at least one success in K trials",
        value_range=(0.0, 1.0),
        higher_is_better=True,
        unit="",
        format_pattern=".4f",
    ),
    MetricType.PASS_POW_K: MetricDefinition(
        name="pass_pow_k",
        display_name="Pass^K",
        category=MetricCategory.TASK,
        description="Probability of all K trials succeeding",
        value_range=(0.0, 1.0),
        higher_is_better=True,
        unit="",
        format_pattern=".4f",
    ),
    MetricType.REWARD: MetricDefinition(
        name="reward",
        display_name="Reward",
        category=MetricCategory.TASK,
        description="Weighted average score from all graders",
        value_range=(0.0, 1.0),
        higher_is_better=True,
        unit="",
        format_pattern=".2f",
    ),
    # Skill tracking metrics
    MetricType.ACCESS_RATE: MetricDefinition(
        name="access_rate",
        display_name="Access Rate",
        category=MetricCategory.SKILL,
        description="Ratio of skill accesses to skill injections (trigger accuracy)",
        value_range=(0.0, 1.0),
        higher_is_better=True,
        unit="%",
        format_pattern=".2%",
    ),
    MetricType.DEEP_USAGE_RATE: MetricDefinition(
        name="deep_usage_rate",
        display_name="Deep Usage Rate",
        category=MetricCategory.SKILL,
        description="Ratio of deep usage (references/scripts) to skill accesses",
        value_range=(0.0, 1.0),
        higher_is_better=True,
        unit="%",
        format_pattern=".2%",
    ),
    MetricType.FALSE_POSITIVE_RATE: MetricDefinition(
        name="false_positive_rate",
        display_name="False Positive Rate",
        category=MetricCategory.SKILL,
        description="Ratio of injected but never accessed skills",
        value_range=(0.0, 1.0),
        higher_is_better=False,
        unit="%",
        format_pattern=".2%",
    ),
    MetricType.EFFECTIVE_USAGE_RATE: MetricDefinition(
        name="effective_usage_rate",
        display_name="Effective Usage Rate",
        category=MetricCategory.SKILL,
        description="Ratio of deep usage to total injections",
        value_range=(0.0, 1.0),
        higher_is_better=True,
        unit="%",
        format_pattern=".2%",
    ),
    MetricType.QUALITY_SCORE: MetricDefinition(
        name="quality_score",
        display_name="Quality Score",
        category=MetricCategory.SKILL,
        description="Composite score: task completion (60%) + efficiency (30%) + trigger accuracy (10%)",
        value_range=(0.0, 1.0),
        higher_is_better=True,
        unit="",
        format_pattern=".2f",
    ),
    MetricType.TASK_COMPLETION_SCORE: MetricDefinition(
        name="task_completion_score",
        display_name="Task Completion Score",
        category=MetricCategory.SKILL,
        description="Average task success rate when skill is available",
        value_range=(0.0, 1.0),
        higher_is_better=True,
        unit="%",
        format_pattern=".2%",
    ),
    MetricType.EFFICIENCY_SCORE: MetricDefinition(
        name="efficiency_score",
        display_name="Efficiency Score",
        category=MetricCategory.SKILL,
        description="Resource efficiency: less context usage and fewer rounds is better",
        value_range=(0.0, 1.0),
        higher_is_better=True,
        unit="",
        format_pattern=".2f",
    ),
}


class MetricsRegistry:
    """Registry for managing evaluation metrics."""

    def __init__(self):
        """Initialize the metrics registry."""
        self._definitions = METRIC_DEFINITIONS.copy()
        self._enabled_metrics: set[MetricType] = set(MetricType)

    def register(self, metric_type: MetricType, definition: MetricDefinition) -> None:
        """Register a new metric definition."""
        self._definitions[metric_type] = definition

    def get_definition(self, metric_type: MetricType) -> MetricDefinition | None:
        """Get definition for a metric type."""
        return self._definitions.get(metric_type)

    def get_all_definitions(self) -> dict[MetricType, MetricDefinition]:
        """Get all metric definitions."""
        return self._definitions.copy()

    def get_metrics_by_category(self, category: MetricCategory) -> list[MetricType]:
        """Get all metrics in a category."""
        return [mt for mt, md in self._definitions.items() if md.category == category]

    def enable_metric(self, metric_type: MetricType) -> None:
        """Enable a metric for collection."""
        self._enabled_metrics.add(metric_type)

    def disable_metric(self, metric_type: MetricType) -> None:
        """Disable a metric from collection."""
        self._enabled_metrics.discard(metric_type)

    def set_enabled_metrics(self, metric_types: list[MetricType]) -> None:
        """Set which metrics are enabled."""
        self._enabled_metrics = set(metric_types)

    def is_enabled(self, metric_type: MetricType) -> bool:
        """Check if a metric is enabled."""
        return metric_type in self._enabled_metrics

    def get_enabled_metrics(self) -> list[MetricType]:
        """Get all enabled metrics."""
        return list(self._enabled_metrics)

    def format_metric(self, metric_type: MetricType, value: float) -> str:
        """Format a metric value using its definition."""
        definition = self.get_definition(metric_type)
        if definition:
            return definition.format_value(value)
        return str(value)

    def get_primary_metric(self, category: MetricCategory) -> MetricType:
        """Get the primary metric for a category."""
        if category == MetricCategory.TASK:
            return MetricType.PASS_RATE
        elif category == MetricCategory.SKILL:
            return MetricType.ACCESS_RATE
        raise ValueError(f"Unknown category: {category}")


# Global registry instance
_registry = MetricsRegistry()


def get_registry() -> MetricsRegistry:
    """Get the global metrics registry."""
    return _registry


def parse_metric_string(metric_str: str) -> MetricType:
    """Parse a metric string to MetricType.

    Args:
        metric_str: String representation of metric (e.g., "pass_rate", "accessRate")

    Returns:
        MetricType enum value

    Raises:
        ValueError: If metric string is not recognized
    """
    # Normalize to snake_case
    normalized = metric_str.lower().replace("-", "_")

    # Try direct match
    try:
        return MetricType(normalized)
    except ValueError:
        pass

    # Try camelCase to snake_case conversion
    snake_case = "".join(
        f"_{c.lower()}" if c.isupper() else c for c in metric_str
    ).lstrip("_")

    try:
        return MetricType(snake_case)
    except ValueError:
        pass

    # Provide helpful error message
    valid_metrics = [mt.value for mt in MetricType]
    raise ValueError(
        f"Unknown metric: '{metric_str}'. Valid metrics: {', '.join(valid_metrics)}"
    )


def get_available_metrics_info() -> str:
    """Get information about all available metrics.

    Returns:
        Formatted string with metric descriptions
    """
    lines = ["Available Metrics:", ""]
    lines.append("Task Evaluation Metrics:")
    for mt in MetricType:
        md = METRIC_DEFINITIONS[mt]
        if md.category == MetricCategory.TASK:
            lines.append(f"  {mt.value:25} - {md.description}")

    lines.append("")
    lines.append("Skill Tracking Metrics:")
    for mt in MetricType:
        md = METRIC_DEFINITIONS[mt]
        if md.category == MetricCategory.SKILL:
            lines.append(f"  {mt.value:25} - {md.description}")

    lines.append("")
    lines.append("Usage:")
    lines.append("  skillgrade eval ./my-skill --metric pass_rate,access_rate")
    lines.append("  skillgrade eval ./my-skill --metric quality_score")

    return "\n".join(lines)


def parse_metrics_list(metrics_str: str) -> list[str]:
    """Parse a comma-separated list of metrics.

    Args:
        metrics_str: Comma-separated metric names

    Returns:
        List of metric names (validated)
    """
    if not metrics_str:
        return []

    metrics = []
    for part in metrics_str.split(","):
        part = part.strip()
        if part:
            # Validate the metric exists
            try:
                mt = parse_metric_string(part)
                metrics.append(mt.value)
            except ValueError as e:
                # Re-raise with context
                raise ValueError(f"Invalid metric '{part}': {e}")

    return metrics
