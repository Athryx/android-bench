from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import typer
from dotenv import load_dotenv
from kbench import BenchmarkRun, Challenge
from kexploit_agent import Limits

from android_bench.catalog import select_challenges
from android_bench.challenge import AndroidAppChallenge
from android_bench.config import BenchmarkConfig
from android_bench.docker import setup_images
from android_bench.runner import (
    resume_benchmark,
    run_benchmark,
    run_test_grader,
)

app = typer.Typer(
    no_args_is_help=True,
    help="Build and run the Challenge 6.1 Android vulnerability benchmark.",
)


@app.callback()
def callback() -> None:
    """Load local environment variables before running a command."""
    load_dotenv()


def _unwrap(val: Any) -> Any:
    if val is None or isinstance(val, (typer.models.OptionInfo, typer.models.ArgumentInfo)):
        return None
    return val


def format_dated_name(base_name: str, now: datetime | None = None) -> str:
    """Format a benchmark run name with date and time to the minute."""
    dt = now or datetime.now().astimezone()
    return f"{base_name} ({dt.strftime('%B')} {dt.day}, {dt.year}, {dt.strftime('%H:%M')})"


@app.command()
def setup() -> None:
    """Build the shared tool image and all 12 challenge images."""
    setup_images()


@app.command("run")
def run_command(
    config: Path = typer.Option(
        ...,
        "--config",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Benchmark JSON configuration.",
    ),
    results: Path = typer.Option(
        ...,
        "--results",
        file_okay=False,
        resolve_path=True,
        help="Results directory (must be empty).",
    ),
    token_limit: int | None = typer.Option(
        None,
        "--token-limit",
        help="Token limit override.",
    ),
    turn_limit: int | None = typer.Option(
        None,
        "--turn-limit",
        help="Turn limit override.",
    ),
    time_limit: float | None = typer.Option(
        None,
        "--time-limit",
        "--timeout",
        help="Time limit override in seconds.",
    ),
    dollar_limit: float | None = typer.Option(
        None,
        "--dollar-limit",
        help="Dollar limit override in USD.",
    ),
) -> None:
    """Run the configured subset, or all challenges when omitted."""
    if results.exists() and any(results.iterdir()):
        raise typer.BadParameter(
            f"results directory {results} must be empty. Use 'android-bench resume {results}' to resume an existing run.",
            param_hint="--results",
        )

    benchmark_config = BenchmarkConfig.from_file(config)
    tok = _unwrap(token_limit)
    turn = _unwrap(turn_limit)
    t_lim = _unwrap(time_limit)
    d_lim = _unwrap(dollar_limit)

    cli_limits: dict[str, Any] = {}
    if tok is not None:
        cli_limits["token_limit"] = tok
    if turn is not None:
        cli_limits["turn_limit"] = turn
    if t_lim is not None:
        cli_limits["time_limit"] = t_lim
    if d_lim is not None:
        cli_limits["dollar_limit"] = Decimal(str(d_lim))

    if cli_limits:
        base_limits = (
            benchmark_config.limits.model_dump()
            if benchmark_config.limits is not None
            else {}
        )
        base_limits.update(cli_limits)
        benchmark_config.limits = Limits(**base_limits)

    results.mkdir(parents=True, exist_ok=True)
    (results / "challenge.json").write_text(benchmark_config.formatted_json())

    dated_name = format_dated_name(benchmark_config.name)

    selected_definitions = tuple(select_challenges(benchmark_config.challenges))
    challenges: list[Challenge] = [
        AndroidAppChallenge(
            definition=definition,
            configured_model=benchmark_config.agent_model_config,
            configured_harness=benchmark_config.harness,
            configured_internet_enabled=benchmark_config.internet_enabled,
            configured_summarize=benchmark_config.summarize,
            configured_limits=benchmark_config.limits,
            max_reprompts=benchmark_config.max_reprompts,
            enabled_capabilities=definition.enabled_capabilities,
        )
        for definition in selected_definitions
    ]
    benchmark_run = BenchmarkRun(
        name=dated_name,
        num_instances=benchmark_config.num_instances,
        challenges=challenges,
        output_folder=results,
    )
    benchmark_result = run_benchmark(
        benchmark_run, benchmark_config=benchmark_config
    )
    typer.echo(benchmark_result.model_dump_json(indent=2))


@app.command("resume")
def resume_command(
    results: Path = typer.Argument(
        None,
        file_okay=False,
        resolve_path=True,
        help="Results directory to resume.",
    ),
    results_opt: Path | None = typer.Option(
        None,
        "--results",
        file_okay=False,
        resolve_path=True,
        help="Results directory (alternative to positional argument).",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Optional benchmark JSON configuration override (defaults to challenge.json in results directory).",
    ),
    token_limit: int | None = typer.Option(
        None,
        "--token-limit",
        help="Token limit override.",
    ),
    turn_limit: int | None = typer.Option(
        None,
        "--turn-limit",
        help="Turn limit override.",
    ),
    time_limit: float | None = typer.Option(
        None,
        "--time-limit",
        "--timeout",
        help="Time limit override in seconds.",
    ),
    dollar_limit: float | None = typer.Option(
        None,
        "--dollar-limit",
        help="Dollar limit override in USD.",
    ),
) -> None:
    """Resume an existing benchmark run."""
    res = _unwrap(results)
    res_opt = _unwrap(results_opt)
    target_results: Path | None = res or res_opt
    if target_results is None:
        raise typer.BadParameter("results directory must be provided", param_hint="results")

    if not target_results.exists() or not target_results.is_dir():
        raise typer.BadParameter(
            f"results directory {target_results} must exist", param_hint="--results"
        )

    resolved_config: Path | None = _unwrap(config)
    config_file = resolved_config or (target_results / "challenge.json")
    if not config_file.is_file():
        raise typer.BadParameter(
            f"challenge.json not found in {target_results}; please specify --config",
            param_hint="--config",
        )

    benchmark_config = BenchmarkConfig.from_file(config_file)
    tok = _unwrap(token_limit)
    turn = _unwrap(turn_limit)
    t_lim = _unwrap(time_limit)
    d_lim = _unwrap(dollar_limit)

    cli_limits: dict[str, Any] = {}
    if tok is not None:
        cli_limits["token_limit"] = tok
    if turn is not None:
        cli_limits["turn_limit"] = turn
    if t_lim is not None:
        cli_limits["time_limit"] = t_lim
    if d_lim is not None:
        cli_limits["dollar_limit"] = Decimal(str(d_lim))

    if cli_limits:
        base_limits = (
            benchmark_config.limits.model_dump()
            if benchmark_config.limits is not None
            else {}
        )
        base_limits.update(cli_limits)
        benchmark_config.limits = Limits(**base_limits)

    selected_definitions = tuple(select_challenges(benchmark_config.challenges))
    challenges: list[Challenge] = [
        AndroidAppChallenge(
            definition=definition,
            configured_model=benchmark_config.agent_model_config,
            configured_harness=benchmark_config.harness,
            configured_internet_enabled=benchmark_config.internet_enabled,
            configured_summarize=benchmark_config.summarize,
            configured_limits=benchmark_config.limits,
            max_reprompts=benchmark_config.max_reprompts,
            enabled_capabilities=definition.enabled_capabilities,
        )
        for definition in selected_definitions
    ]
    dated_name = format_dated_name(benchmark_config.name)
    benchmark_run = BenchmarkRun(
        name=dated_name,
        num_instances=benchmark_config.num_instances,
        challenges=challenges,
        output_folder=target_results,
    )
    benchmark_result = resume_benchmark(
        benchmark_run, benchmark_config=benchmark_config
    )
    typer.echo(benchmark_result.model_dump_json(indent=2))


@app.command("test-grader")
def test_grader_command(
    results: Path = typer.Argument(
        None,
        file_okay=False,
        resolve_path=True,
        help="Results directory containing challenge solutions to grade.",
    ),
    results_opt: Path | None = typer.Option(
        None,
        "--results",
        file_okay=False,
        resolve_path=True,
        help="Results directory (alternative to positional argument).",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Optional benchmark JSON configuration override (defaults to challenge.json in results directory).",
    ),
) -> None:
    """Run the grader against existing challenge solutions in a results directory."""
    res = _unwrap(results)
    res_opt = _unwrap(results_opt)
    target_results: Path | None = res or res_opt
    if target_results is None:
        raise typer.BadParameter("results directory must be provided", param_hint="results")

    if not target_results.exists() or not target_results.is_dir():
        raise typer.BadParameter(
            f"results directory {target_results} must exist", param_hint="--results"
        )

    resolved_config: Path | None = _unwrap(config)
    config_file = resolved_config or (target_results / "challenge.json")
    if not config_file.is_file():
        raise typer.BadParameter(
            f"challenge.json not found in {target_results}; please specify --config",
            param_hint="--config",
        )

    benchmark_config = BenchmarkConfig.from_file(config_file)
    selected_definitions = tuple(
        defn
        for defn in select_challenges(benchmark_config.challenges)
        if (target_results / defn.name.value).is_dir()
    )
    if not selected_definitions:
        raise typer.BadParameter(
            f"no challenge solution directories found in {target_results}",
            param_hint="--results",
        )

    challenges: list[Challenge] = [
        AndroidAppChallenge(
            definition=definition,
            configured_model=benchmark_config.agent_model_config,
            configured_harness=benchmark_config.harness,
            configured_internet_enabled=benchmark_config.internet_enabled,
            configured_summarize=benchmark_config.summarize,
            configured_limits=benchmark_config.limits,
            max_reprompts=benchmark_config.max_reprompts,
            enabled_capabilities=definition.enabled_capabilities,
        )
        for definition in selected_definitions
    ]
    dated_name = format_dated_name(benchmark_config.name)
    benchmark_run = BenchmarkRun(
        name=dated_name,
        num_instances=benchmark_config.num_instances,
        challenges=challenges,
        output_folder=target_results,
    )
    test_grader_result = run_test_grader(benchmark_run)
    typer.echo(test_grader_result.model_dump_json(indent=2))


test_grader_command.__test__ = False  # type: ignore[attr-defined]


def main() -> None:
    app()
