"""Commands module for skillevol."""

import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from skillevol.core.decision import DecisionEngine
from skillevol.core.evaluator import Evaluator
from skillevol.core.explorer import Explorer
from skillevol.core.llm import LLMClient
from skillevol.core.types import EvalConfig, EvolState, ExplorerConfig, EvalResult, OperatorType

console = Console()


async def run_evolve(
    skill_path: Path,
    eval_config: Optional[Path] = None,
    trials: int = 5,
    max_iterations: int = 100,
    max_time: int = 3600,
    patience: int = 20,
    strategy: str = "hybrid",
    program_md: Optional[Path] = None,
    llm_model: str = "gpt-4o",
    keep_workspace: bool = False,
    verbose: bool = False,
) -> None:
    """Run skill evolution.

    Args:
        skill_path: Path to skill directory containing SKILL.md
        eval_config: Optional path to eval.yaml
        trials: Number of evaluation trials
        max_iterations: Maximum evolution iterations
        max_time: Maximum time in seconds
        patience: Stop after N consecutive no-improvements
        strategy: Evolution strategy (hybrid, autonomous, structured)
        program_md: Optional path to program.md
        llm_model: LLM model name
        keep_workspace: Keep workspaces after completion
        verbose: Verbose output
    """
    skill_file = skill_path / "SKILL.md"
    if not skill_file.exists():
        console.print(f"[red]Error: SKILL.md not found in {skill_path}[/red]")
        raise SystemExit(1)

    eval_config_path = eval_config or skill_path / "eval.yaml"
    if eval_config_path and not eval_config_path.exists():
        console.print(f"[yellow]Warning: eval.yaml not found at {eval_config_path}[/yellow]")
        console.print("[yellow]Will attempt to run without eval.yaml[/yellow]")

    workspace_dir = Path(f"/tmp/skill-evol/{skill_path.name}")
    workspace_dir.mkdir(parents=True, exist_ok=True)

    results_dir = skill_path / "results"
    results_dir.mkdir(exist_ok=True)

    program_md_content = None
    if program_md and program_md.exists():
        program_md_content = program_md.read_text()

    console.print("[bold cyan]Skill Evol[/bold cyan] - Autonomous skill optimization")
    console.print(f"  Skill: {skill_path}")
    console.print(f"  Strategy: {strategy}")
    console.print(f"  Trials: {trials}")
    console.print()

    llm_client = LLMClient(model=llm_model)
    eval_config_obj = EvalConfig(
        skill_path=skill_path,
        eval_config_path=eval_config_path if eval_config_path and eval_config_path.exists() else None,
        trials=trials,
    )
    explorer_config = ExplorerConfig(
        strategy=strategy,
        llm_model=llm_model,
    )

    evaluator = Evaluator(eval_config_obj)
    explorer = Explorer(llm_client, explorer_config, eval_config_obj, program_md_content)
    decision_engine = DecisionEngine()

    current_skill_md = skill_file.read_text()

    baseline_result = await _run_baseline_evaluation(evaluator, current_skill_md)
    if baseline_result is None:
        console.print("[red]Baseline evaluation failed. Exiting.[/red]")
        raise SystemExit(1)

    state = EvolState(
        current_skill_md=current_skill_md,
        best_skill_md=current_skill_md,
        best_score=baseline_result.combined_score,
        iteration=0,
        consecutive_no_improve=0,
        experiment_history=[],
    )

    results_file = results_dir / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tsv"
    _write_results_header(results_file)

    start_time = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Evolving skill...", total=max_iterations)

        while state.iteration < max_iterations:
            elapsed = time.time() - start_time
            if elapsed > max_time:
                console.print("\n[yellow]Max time reached. Stopping.[/yellow]")
                break
            if state.consecutive_no_improve >= patience:
                console.print(f"\n[yellow]Patience reached ({patience}). Stopping.[/yellow]")
                break

            progress.update(
                task, description=f"Iteration {state.iteration + 1} | Score: {state.best_score:.3f}"
            )

            # Get the most recent evaluation result for diagnostics
            current_result = baseline_result
            if state.experiment_history:
                # Use the most recent result from history
                latest_record = state.experiment_history[-1]
                current_result = EvalResult(
                    pass_rate=latest_record.pass_rate,
                    pass_at_k=latest_record.pass_at_k,
                    pass_pow_k=latest_record.pass_pow_k,
                    reward=latest_record.reward,
                    access_rate=latest_record.access_rate,
                    deep_usage_rate=latest_record.deep_usage_rate,
                    false_positive_rate=latest_record.false_positive_rate,
                    effective_usage_rate=latest_record.effective_usage_rate,
                    quality_score=latest_record.quality_score,
                )
                current_result.combined_score = latest_record.combined_score

            new_skill_md, op_type, changes_summary = explorer.propose(
                state.current_skill_md,
                current_result,
                [r for _, r in _get_history_results(state)],
                state.consecutive_no_improve,
            )

            if new_skill_md == state.current_skill_md:
                state.iteration += 1
                progress.advance(task)
                continue

            new_result = await evaluator.evaluate(new_skill_md)

            keep, new_state = decision_engine.judge(
                state,
                new_result,
                new_skill_md,
                f"{state.iteration + 1:03d}",
                op_type,
                changes_summary,
            )

            experiment_record = new_state.experiment_history[-1]
            experiment_record.timestamp = datetime.now()
            _write_result_row(results_file, experiment_record)

            if keep:
                console.print(
                    f"\n[green]✓ Improved![/green] {new_result.combined_score:.3f} > {state.best_score:.3f}"
                )
                if verbose:
                    console.print(f"  Operator: {op_type.value}")
                    console.print(f"  Changes: {changes_summary}")
                # Track operator effectiveness
                explorer.record_operator_result(op_type, improved=True)
            else:
                status = (
                    "[yellow]→ Neutral[/yellow]"
                    if new_result.combined_score >= state.best_score - 0.01
                    else "[red]✗ Reverted[/red]"
                )
                console.print(f"\n{status} {new_result.combined_score:.3f}")
                # Track operator effectiveness (neutral counts as not improved)
                explorer.record_operator_result(op_type, improved=False)

            state = new_state
            state.iteration += 1
            progress.advance(task)

            if keep_workspace and keep:
                _save_skill_md(workspace_dir / f"best_iteration_{state.iteration}", new_skill_md)

    progress.update(task, completed=max_iterations)

    console.print()
    _print_summary(state, results_file)


async def _run_baseline_evaluation(evaluator: Evaluator, skill_md: str) -> Optional[EvalResult]:
    """Run baseline evaluation."""
    console.print("[cyan]Running baseline evaluation...[/cyan]")
    try:
        result = await evaluator.evaluate(skill_md)
        console.print(
            f"[green]Baseline: pass_rate={result.pass_rate:.2%}, pass_at_k={result.pass_at_k:.2%}, combined={result.combined_score:.3f}[/green]"
        )
        return result
    except Exception as e:
        console.print(f"[red]Baseline evaluation failed: {e}[/red]")
        return None


def _get_history_results(state: EvolState) -> list[tuple[str, EvalResult]]:
    """Get history results as list of tuples."""
    return [(r.experiment_id, r) for r in state.experiment_history]


def _write_results_header(path: Path) -> None:
    """Write TSV header with all metrics."""
    header = (
        "experiment_id\ttimestamp\toperator\t"
        "pass_rate\tpass_at_k\tpass_pow_k\treward\t"
        "access_rate\tdeep_usage_rate\tfalse_positive_rate\teffective_usage_rate\tquality_score\t"
        "combined_score\tchanges_summary\n"
    )
    path.write_text(header)


def _write_result_row(path: Path, record) -> None:
    """Write a result row to TSV with all metrics."""
    with open(path, "a") as f:
        f.write(
            f"{record.experiment_id}\t{record.timestamp.isoformat()}\t{record.operator_type.value}\t"
            f"{record.pass_rate:.4f}\t{record.pass_at_k:.4f}\t{record.pass_pow_k:.4f}\t{record.reward:.4f}\t"
            f"{record.access_rate:.4f}\t{record.deep_usage_rate:.4f}\t{record.false_positive_rate:.4f}\t"
            f"{record.effective_usage_rate:.4f}\t{record.quality_score:.4f}\t"
            f"{record.combined_score:.4f}\t{record.changes_summary}\n"
        )


def _save_skill_md(path: Path, content: str) -> None:
    """Save SKILL.md to a directory."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(content)


def _print_summary(state: EvolState, results_file: Path) -> None:
    """Print evolution summary."""
    table = Table(title="Evolution Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total iterations", str(state.iteration))
    table.add_row("Best combined score", f"{state.best_score:.4f}")
    if state.experiment_history:
        table.add_row("Best pass_rate", f"{max(r.pass_rate for r in state.experiment_history):.2%}")
        table.add_row("Best pass_at_k", f"{max(r.pass_at_k for r in state.experiment_history):.2%}")
    table.add_row("Results file", str(results_file))

    console.print(table)
