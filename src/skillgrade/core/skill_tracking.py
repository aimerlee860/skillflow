"""Skill tracking module for monitoring skill file access."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..types import (
    SkillAccessRecord,
    SkillAccessType,
    SkillActivationStatus,
    SkillTrackingSession,
    SkillTrackingReport,
)


class SkillTracker:
    """Tracks skill file access during agent execution."""

    def __init__(self, skill_paths: list[str], workspace: Path, trial_index: int = 0):
        """Initialize skill tracker.

        Args:
            skill_paths: List of skill directory paths
            workspace: Path to the agent workspace
            trial_index: Current trial index
        """
        self.skill_paths = skill_paths
        self.workspace = workspace
        self._trial_index = trial_index
        self._sessions: dict[str, SkillTrackingSession] = {}

        # Initialize sessions for all injected skills
        for skill_path in skill_paths:
            skill_name = Path(skill_path).name
            self._initialize_session(skill_name, skill_path)

    def set_trial_index(self, index: int) -> None:
        """Set current trial index."""
        self._trial_index = index

    def _initialize_session(self, skill_name: str, skill_path: str) -> None:
        """Initialize tracking session for a skill."""
        session = SkillTrackingSession(
            trial_index=self._trial_index,
            skill_name=skill_name,
            skill_path=skill_path,
            activation_status=SkillActivationStatus.INJECTED,
            injected_in_prompt=True,
        )
        self._sessions[skill_name] = session

    def detect_skill_from_path(
        self, file_path: str
    ) -> tuple[str | None, SkillAccessType | None]:
        """Detect if a file path belongs to a skill.

        Args:
            file_path: Path to check

        Returns:
            Tuple of (skill_name, access_type) or (None, None)
        """
        path = Path(file_path).resolve()

        for skill_path in self.skill_paths:
            skill_dir = Path(skill_path).resolve()
            try:
                relative = path.relative_to(skill_dir)
                relative_str = str(relative)

                if relative_str == "SKILL.md":
                    return skill_dir.name, SkillAccessType.SKILL_MD
                elif relative_str.startswith("references/") or relative_str.startswith(
                    "references\\"
                ):
                    return skill_dir.name, SkillAccessType.REFERENCE
                elif relative_str.startswith("scripts/") or relative_str.startswith(
                    "scripts\\"
                ):
                    return skill_dir.name, SkillAccessType.SCRIPT
                elif relative_str.startswith("assets/") or relative_str.startswith(
                    "assets\\"
                ):
                    return skill_dir.name, SkillAccessType.ASSET
            except ValueError:
                continue

        return None, None

    def record_access(
        self,
        file_path: str,
        tool_used: str,
        skill_name: str | None = None,
        access_type: SkillAccessType | None = None,
    ) -> SkillAccessRecord | None:
        """Record a skill file access.

        Args:
            file_path: Path to the accessed file
            tool_used: Tool that accessed the file
            skill_name: Optional pre-detected skill name
            access_type: Optional pre-detected access type

        Returns:
            SkillAccessRecord if access was to a skill file, None otherwise
        """
        # Auto-detect if not provided
        if skill_name is None or access_type is None:
            skill_name, access_type = self.detect_skill_from_path(file_path)

        if skill_name is None or access_type is None:
            return None

        # Create access record
        record = SkillAccessRecord(
            skill_name=skill_name,
            access_type=access_type,
            file_path=file_path,
            timestamp=time.time(),
            tool_used=tool_used,
        )

        # Update or create session
        if skill_name not in self._sessions:
            # Skill was accessed but not explicitly injected (dynamic discovery)
            skill_path = str(Path(file_path).parent.parent)
            self._initialize_session(skill_name, skill_path)
            self._sessions[skill_name].injected_in_prompt = False

        session = self._sessions[skill_name]
        session.access_records.append(record)

        # Update timing
        if session.first_access_time is None:
            session.first_access_time = record.timestamp
        session.last_access_time = record.timestamp

        # Update access depth
        self._update_access_depth(session)

        return record

    def _update_access_depth(self, session: SkillTrackingSession) -> None:
        """Update the access depth for a session."""
        has_skill_md = any(
            r.access_type == SkillAccessType.SKILL_MD for r in session.access_records
        )
        has_deep = any(
            r.access_type in (SkillAccessType.REFERENCE, SkillAccessType.SCRIPT)
            for r in session.access_records
        )

        if has_deep:
            session.access_depth = 2
            session.activation_status = SkillActivationStatus.DEEP_USAGE
        elif has_skill_md:
            session.access_depth = 1
            session.activation_status = SkillActivationStatus.ACCESSED
        else:
            session.access_depth = 0

    def get_session(self, skill_name: str) -> SkillTrackingSession | None:
        """Get tracking session for a skill."""
        return self._sessions.get(skill_name)

    def get_all_sessions(self) -> list[SkillTrackingSession]:
        """Get all tracking sessions."""
        return list(self._sessions.values())

    def generate_report(self) -> list[SkillTrackingReport]:
        """Generate aggregated reports for all tracked skills."""
        reports = []

        for skill_name, session in self._sessions.items():
            injected = 1 if session.injected_in_prompt else 0
            accessed = 1 if session.access_depth >= 1 else 0
            deep_usage = 1 if session.access_depth >= 2 else 0

            # Count access types
            skill_md_reads = sum(
                1 for r in session.access_records if r.access_type == SkillAccessType.SKILL_MD
            )
            reference_reads = sum(
                1 for r in session.access_records if r.access_type == SkillAccessType.REFERENCE
            )
            script_accesses = sum(
                1 for r in session.access_records if r.access_type == SkillAccessType.SCRIPT
            )
            asset_accesses = sum(
                1 for r in session.access_records if r.access_type == SkillAccessType.ASSET
            )

            # Calculate rates
            access_rate = accessed / injected if injected > 0 else 0.0
            deep_usage_rate = deep_usage / accessed if accessed > 0 else 0.0
            false_positive_rate = (injected - accessed) / injected if injected > 0 else 0.0
            effective_usage_rate = deep_usage / injected if injected > 0 else 0.0

            report = SkillTrackingReport(
                skill_name=skill_name,
                total_trials=1,
                injected_count=injected,
                accessed_count=accessed,
                deep_usage_count=deep_usage,
                access_rate=access_rate,
                deep_usage_rate=deep_usage_rate,
                false_positive_rate=false_positive_rate,
                effective_usage_rate=effective_usage_rate,
                skill_md_reads=skill_md_reads,
                reference_reads=reference_reads,
                script_accesses=script_accesses,
                asset_accesses=asset_accesses,
            )
            reports.append(report)

        return reports


def aggregate_reports(
    trial_results: list[dict],
) -> list[SkillTrackingReport]:
    """Aggregate skill tracking data from multiple trial result dicts.

    Args:
        trial_results: List of trial result dicts (from TrialResult.to_dict())
                       Each dict contains a "skillTracking" key with list of session dicts

    Returns:
        List of aggregated SkillTrackingReport
    """
    # Collect all skill tracking sessions across all trials
    all_sessions: list[dict] = []

    for trial in trial_results:
        # Each trial dict has "skillTracking" key with list of session dicts
        tracking_sessions = trial.get("skillTracking", [])
        all_sessions.extend(tracking_sessions)

    if not all_sessions:
        return []

    # Group by skill name (using camelCase key from to_dict())
    skill_data: dict[str, list[dict]] = {}
    for session in all_sessions:
        skill_name = session.get("skillName")
        if skill_name is None:
            continue
        if skill_name not in skill_data:
            skill_data[skill_name] = []
        skill_data[skill_name].append(session)

    aggregated = []
    for skill_name, sessions in skill_data.items():
        total_trials = len(sessions)
        injected_count = sum(1 for s in sessions if s.get("injectedInPrompt", False))
        accessed_count = sum(1 for s in sessions if s.get("activationStatus") in ("accessed", "deep_usage"))
        deep_usage_count = sum(1 for s in sessions if s.get("activationStatus") == "deep_usage")

        # Sum up access records by type
        skill_md_reads = 0
        reference_reads = 0
        script_accesses = 0
        asset_accesses = 0

        for session in sessions:
            for record in session.get("accessRecords", []):
                access_type = record.get("accessType")
                if access_type == "skill_md":
                    skill_md_reads += 1
                elif access_type == "reference":
                    reference_reads += 1
                elif access_type == "script":
                    script_accesses += 1
                elif access_type == "asset":
                    asset_accesses += 1

        # Calculate aggregated rates
        access_rate = accessed_count / injected_count if injected_count > 0 else 0.0
        deep_usage_rate = deep_usage_count / accessed_count if accessed_count > 0 else 0.0
        false_positive_rate = (
            (injected_count - accessed_count) / injected_count if injected_count > 0 else 0.0
        )
        effective_usage_rate = deep_usage_count / injected_count if injected_count > 0 else 0.0

        report = SkillTrackingReport(
            skill_name=skill_name,
            total_trials=total_trials,
            injected_count=injected_count,
            accessed_count=accessed_count,
            deep_usage_count=deep_usage_count,
            access_rate=access_rate,
            deep_usage_rate=deep_usage_rate,
            false_positive_rate=false_positive_rate,
            effective_usage_rate=effective_usage_rate,
            skill_md_reads=skill_md_reads,
            reference_reads=reference_reads,
            script_accesses=script_accesses,
            asset_accesses=asset_accesses,
        )
        aggregated.append(report)

    return aggregated
