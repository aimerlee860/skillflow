"""Core module initialization."""

from .config import (
    load_eval_config,
    load_eval_config_from_path,
    parse_eval_config,
    normalize_grader_weights,
    save_report,
    save_eval_config,
)
from .skills import detect_skills, get_skill_dir
from .workspace import create_temp_workspace, cleanup_workspace, read_env_file
from .runner import EvalRunner, get_default_output_dir
from .skill_tracking import SkillTracker, aggregate_reports
from .skill_stats import (
    SkillStatistics,
    calculate_skill_statistics,
    format_statistics_report,
    format_tracking_summary,
)
from .metrics import (
    MetricCategory,
    MetricType,
    MetricDefinition,
    MetricsRegistry,
    get_registry,
    parse_metric_string,
    parse_metrics_list,
    get_available_metrics_info,
    METRIC_DEFINITIONS,
)
# Skill context and analysis
from .context import SkillContext, SkillContextExtractor
from .difficulty import DifficultyAssessment, LLMDifficultyAssessor
from .deduplication import DuplicationCheck, LLMTaskDeduplicator
# Smart test generation
from .understanding import SkillUnderstandingAnalyzer
from .planning import TestPlanner
from .generator import TestCase, TestCaseGenerator, generate_eval_plan

__all__ = [
    # Config
    "load_eval_config",
    "load_eval_config_from_path",
    "parse_eval_config",
    "normalize_grader_weights",
    "save_report",
    "save_eval_config",
    # Skills
    "detect_skills",
    "get_skill_dir",
    # Workspace
    "create_temp_workspace",
    "cleanup_workspace",
    "read_env_file",
    # Runner
    "EvalRunner",
    "get_default_output_dir",
    # Skill tracking
    "SkillTracker",
    "aggregate_reports",
    "SkillStatistics",
    "calculate_skill_statistics",
    "format_statistics_report",
    "format_tracking_summary",
    # Metrics
    "MetricCategory",
    "MetricType",
    "MetricDefinition",
    "MetricsRegistry",
    "get_registry",
    "parse_metric_string",
    "parse_metrics_list",
    "get_available_metrics_info",
    "METRIC_DEFINITIONS",
    # Context and analysis
    "SkillContext",
    "SkillContextExtractor",
    "DifficultyAssessment",
    "LLMDifficultyAssessor",
    "DuplicationCheck",
    "LLMTaskDeduplicator",
    # Smart test generation
    "SkillUnderstandingAnalyzer",
    "TestPlanner",
    "TestCase",
    "TestCaseGenerator",
    "generate_eval_plan",
]
