"""Decision engine - judge whether to keep or revert changes."""

import datetime

from skillevol.core.types import EvalResult, EvolState, EvolutionMode, ExperimentRecord, OperatorType


class DecisionEngine:
    def __init__(self, threshold: float = 0.01, mode: str = "steady"):
        self.threshold = threshold
        self.mode = EvolutionMode(mode)

    def judge(
        self,
        state: EvolState,
        new_result: EvalResult,
        new_skill_md: str,
        experiment_id: str,
        operator_type: OperatorType,
        changes_summary: str,
    ) -> tuple[bool, EvolState]:
        if self.mode == EvolutionMode.STEADY:
            return self._judge_steady(state, new_result, new_skill_md, experiment_id, operator_type, changes_summary)
        else:
            return self._judge_greedy(state, new_result, new_skill_md, experiment_id, operator_type, changes_summary)

    def _judge_steady(
        self,
        state: EvolState,
        new_result: EvalResult,
        new_skill_md: str,
        experiment_id: str,
        operator_type: OperatorType,
        changes_summary: str,
    ) -> tuple[bool, EvolState]:
        """Steady mode: compare against baseline, always evolve from baseline."""
        improved = new_result.combined_score > state.baseline_score + self.threshold

        record = ExperimentRecord(
            experiment_id=experiment_id,
            timestamp=state.experiment_history[-1].timestamp
            if state.experiment_history
            else datetime.datetime.now(),
            operator_type=operator_type,
            pass_rate=new_result.pass_rate,
            pass_at_k=new_result.pass_at_k,
            pass_pow_k=new_result.pass_pow_k,
            reward=new_result.reward,
            access_rate=new_result.access_rate,
            deep_usage_rate=new_result.deep_usage_rate,
            false_positive_rate=new_result.false_positive_rate,
            effective_usage_rate=new_result.effective_usage_rate,
            quality_score=new_result.quality_score,
            combined_score=new_result.combined_score,
            changes_summary=changes_summary,
            skill_md_before=state.baseline_skill_md,  # Always compare against baseline
            skill_md_after=new_skill_md,
        )

        if improved:
            return True, EvolState(
                current_skill_md=state.baseline_skill_md,  # Always reset to baseline for next iteration
                best_skill_md=new_skill_md,
                best_score=new_result.combined_score,
                baseline_skill_md=state.baseline_skill_md,
                baseline_score=state.baseline_score,
                iteration=state.iteration + 1,
                consecutive_no_improve=0,
                experiment_history=[*state.experiment_history, record],
            )
        else:
            return False, EvolState(
                current_skill_md=state.baseline_skill_md,  # Reset to baseline
                best_skill_md=state.best_skill_md,
                best_score=state.best_score,
                baseline_skill_md=state.baseline_skill_md,
                baseline_score=state.baseline_score,
                iteration=state.iteration + 1,
                consecutive_no_improve=state.consecutive_no_improve + 1,
                experiment_history=[*state.experiment_history, record],
            )

    def _judge_greedy(
        self,
        state: EvolState,
        new_result: EvalResult,
        new_skill_md: str,
        experiment_id: str,
        operator_type: OperatorType,
        changes_summary: str,
    ) -> tuple[bool, EvolState]:
        """Greedy mode: compare against current best, evolve from best."""
        improved = new_result.combined_score > state.best_score + self.threshold
        regression = new_result.combined_score < state.best_score - self.threshold

        record = ExperimentRecord(
            experiment_id=experiment_id,
            timestamp=state.experiment_history[-1].timestamp
            if state.experiment_history
            else datetime.datetime.now(),
            operator_type=operator_type,
            pass_rate=new_result.pass_rate,
            pass_at_k=new_result.pass_at_k,
            pass_pow_k=new_result.pass_pow_k,
            reward=new_result.reward,
            access_rate=new_result.access_rate,
            deep_usage_rate=new_result.deep_usage_rate,
            false_positive_rate=new_result.false_positive_rate,
            effective_usage_rate=new_result.effective_usage_rate,
            quality_score=new_result.quality_score,
            combined_score=new_result.combined_score,
            changes_summary=changes_summary,
            skill_md_before=state.current_skill_md,
            skill_md_after=new_skill_md,
        )

        if improved:
            return True, self._keep_change(state, new_skill_md, new_result, record)
        elif regression:
            return False, self._revert_change(state, record)
        else:
            return False, self._neutral_change(state, new_skill_md, new_result, record)

    def _keep_change(
        self,
        state: EvolState,
        new_skill_md: str,
        new_result: EvalResult,
        record: ExperimentRecord,
    ) -> EvolState:
        return EvolState(
            current_skill_md=new_skill_md,
            best_skill_md=new_skill_md,
            best_score=new_result.combined_score,
            baseline_skill_md=state.baseline_skill_md,
            baseline_score=state.baseline_score,
            iteration=state.iteration + 1,
            consecutive_no_improve=0,
            experiment_history=[*state.experiment_history, record],
        )

    def _revert_change(
        self,
        state: EvolState,
        record: ExperimentRecord,
    ) -> EvolState:
        return EvolState(
            current_skill_md=state.best_skill_md,
            best_skill_md=state.best_skill_md,
            best_score=state.best_score,
            baseline_skill_md=state.baseline_skill_md,
            baseline_score=state.baseline_score,
            iteration=state.iteration + 1,
            consecutive_no_improve=state.consecutive_no_improve + 1,
            experiment_history=[*state.experiment_history, record],
        )

    def _neutral_change(
        self,
        state: EvolState,
        new_skill_md: str,
        new_result: EvalResult,
        record: ExperimentRecord,
    ) -> EvolState:
        return EvolState(
            current_skill_md=new_skill_md,
            best_skill_md=state.best_skill_md,
            best_score=state.best_score,
            baseline_skill_md=state.baseline_skill_md,
            baseline_score=state.baseline_score,
            iteration=state.iteration + 1,
            consecutive_no_improve=state.consecutive_no_improve + 1,
            experiment_history=[*state.experiment_history, record],
        )
