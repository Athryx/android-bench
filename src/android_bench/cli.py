from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from dotenv import load_dotenv
from kbench import BenchmarkRun, Challenge

from android_bench.catalog import select_challenges
from android_bench.challenge import AndroidAppChallenge
from android_bench.config import BenchmarkConfig
from android_bench.docker import setup_images
from android_bench.runner import run_benchmark

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
        help="New or empty results directory.",
    ),
) -> None:
    """Run the configured subset, or all challenges when omitted."""
    if results.exists() and any(results.iterdir()):
        raise typer.BadParameter("results directory must be empty", param_hint="--results")

    benchmark_config = BenchmarkConfig.from_file(config)
    now = datetime.now().astimezone()
    dated_name = f"{benchmark_config.name} ({now.strftime('%B')} {now.day}, {now.year})"
    challenges: list[Challenge] = [
        AndroidAppChallenge(
            definition=definition,
            configured_model=benchmark_config.agent_model_config,
            configured_harness=benchmark_config.harness,
            max_reprompts=benchmark_config.max_reprompts,
        )
        for definition in select_challenges(benchmark_config.challenges)
    ]
    result = run_benchmark(
        BenchmarkRun(
            name=dated_name,
            num_instances=benchmark_config.num_instances,
            challenges=challenges,
            output_folder=results,
        )
    )
    typer.echo(result.model_dump_json(indent=2))


def main() -> None:
    app()
