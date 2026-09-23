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
from android_bench.runner import run_benchmark, run_test_grader

app = typer.Typer(
    no_args_is_help=True,
    help="Build and run the Challenge 6.1 Android vulnerability benchmark.",
)


@app.callback()
def callback() -> None:
    """Load local environment variables before running a command."""
    load_dotenv()


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
        help="Results directory (empty for run, existing for --test-grader).",
    ),
    test_grader: bool = typer.Option(
        False,
        "--test-grader",
        help="Run the grader against existing results instead of running the benchmark.",
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
    is_test_grader = bool(test_grader) and not isinstance(
        test_grader, typer.models.OptionInfo
    )
    if not is_test_grader:
        if results.exists() and any(results.iterdir()):
            raise typer.BadParameter("results directory must be empty", param_hint="--results")
    else:
        if not results.exists() or not results.is_dir():
            raise typer.BadParameter(
                "results directory must exist when using --test-grader", param_hint="--results"
            )

    benchmark_config = BenchmarkConfig.from_file(config)
    def _unwrap(val: Any) -> Any:
        if val is None or isinstance(val, typer.models.OptionInfo):
            return None
        return val

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

    now = datetime.now().astimezone()
    dated_name = f"{benchmark_config.name} ({now.strftime('%B')} {now.day}, {now.year})"

    selected_definitions = tuple(select_challenges(benchmark_config.challenges))
    if is_test_grader:
        selected_definitions = tuple(
            defn for defn in selected_definitions if (results / defn.name.value).is_dir()
        )
        if not selected_definitions:
            raise typer.BadParameter(
                f"no challenge solution directories found in {results}", param_hint="--results"
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
    benchmark_run = BenchmarkRun(
        name=dated_name,
        num_instances=benchmark_config.num_instances,
        challenges=challenges,
        output_folder=results,
    )
    if is_test_grader:
        test_grader_result = run_test_grader(benchmark_run)
        typer.echo(test_grader_result.model_dump_json(indent=2))
    else:
        benchmark_result = run_benchmark(benchmark_run)
        typer.echo(benchmark_result.model_dump_json(indent=2))


def main() -> None:
    app()
