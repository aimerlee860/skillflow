"""Trigger grader - evaluates skill trigger based on SKILL.md access."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..types import GraderConfig, GraderResult
from .base import BaseGrader


class TriggerGrader(BaseGrader):
    """Grader that evaluates skill trigger based on SKILL.md access.

    This grader checks whether the skill was actually triggered by examining
    the skill_tracking logs. It determines if SKILL.md was read (triggered)
    or not (not triggered).

    Key distinction:
    - INJECTED: Skill was injected into prompt (not a trigger)
    - ACCESSED: SKILL.md was read (skill triggered)
    - DEEP_USAGE: Deep usage of references/scripts (skill triggered)
    """

    async def grade(
        self,
        workspace: Path | str,
        config: GraderConfig,
        logs: list[dict[str, Any]],
    ) -> GraderResult:
        """Evaluate skill trigger based on SKILL.md access.

        Args:
            workspace: Path to the workspace directory
            config: Grader configuration with expected_trigger field
            logs: Execution logs from the agent

        Returns:
            GraderResult with score based on trigger correctness
        """
        # 1. Extract skill_tracking data from logs
        skill_tracking = [
            log.get("data", {})
            for log in logs
            if log.get("type") == "skill_tracking"
        ]

        # 2. Determine if skill was actually triggered
        triggered = self._is_skill_triggered(skill_tracking)

        # 3. Get expected trigger status
        expected_trigger = config.expected_trigger if config.expected_trigger is not None else True

        # 4. Calculate score based on match
        if expected_trigger:
            # Positive test: skill should trigger
            if triggered:
                score = 1.0
                details = "技能正确触发"
                reasoning = "SKILL.md 被读取，表明技能被正确识别和使用。"
            else:
                score = 0.0
                details = "假阴性：技能未在应该触发时触发"
                reasoning = "SKILL.md 未被读取，技能未被识别或使用。这是一个假阴性错误。"
        else:
            # Negative test: skill should NOT trigger
            if not triggered:
                score = 1.0
                details = "正确：技能未触发"
                reasoning = "SKILL.md 未被读取，技能正确地没有被触发。"
            else:
                score = 0.0
                details = "假阳性：技能被错误触发"
                reasoning = "SKILL.md 被读取，但这是一个负向测试用例，技能不应该被触发。这是一个假阳性错误。"

        return GraderResult(
            grader_type="trigger",
            score=score,
            weight=config.weight,
            details=details,
            reasoning=reasoning,
            checks=[
                {
                    "name": "trigger_check",
                    "passed": triggered == expected_trigger,
                    "expected": "触发" if expected_trigger else "不触发",
                    "actual": "触发" if triggered else "不触发",
                }
            ],
        )

    def _is_skill_triggered(self, skill_tracking: list[dict[str, Any]]) -> bool:
        """Check if skill was triggered by examining SKILL.md access.

        Args:
            skill_tracking: List of skill tracking session data

        Returns:
            True if SKILL.md was accessed (triggered), False otherwise
        """
        for session in skill_tracking:
            activation_status = session.get("activationStatus", "")
            # ACCESSED = SKILL.md was read
            # DEEP_USAGE = deep usage of references/scripts
            if activation_status in ("accessed", "deep_usage"):
                return True

        return False
