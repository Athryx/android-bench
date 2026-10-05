from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import typer
from dotenv import load_dotenv
from kbench import BenchmarkRun, Challenge
from kexploit_agent import Limits
from ksandbox.logging_utils import configure_logging

from android_bench.catalog import ChallengeDefinition, select_challenges
from android_bench.challenge import AndroidAppChallenge
from android_bench.config import BenchmarkConfig
from android_bench.docker import setup_images
from android_bench.models import ChallengeResumeConfig, ResumeMode
from android_bench.runner import (
    resume_benchmark,
    run_benchmark,
    run_grader,
    run_test_grader,
)


def _build_challenges_for_config(
    benchmark_config: BenchmarkConfig,
    definitions: tuple[ChallengeDefinition, ...],
) -> list[Challenge]:
    overrides_by_name = {
        cfg.name: cfg
        for cfg in benchmark_config.challenge_configs
    }
    challenges: list[Challenge] = []
    for definition in definitions:
        cfg = overrides_by_name.get(definition.name)
        enabled_capabilities = (
            tuple(cfg.capabilities)
            if cfg is not None and cfg.capabilities is not None
            else definition.enabled_capabilities
        )
        solutions_folder = cfg.solutions_folder if cfg is not None else None
        extra_prompt = cfg.extra_prompt if cfg is not None else None
        challenges.append(
            AndroidAppChallenge(
                definition=definition,
                configured_model=benchmark_config.agent_model_config,
                configured_harness=benchmark_config.harness,
                configured_internet_enabled=benchmark_config.internet_enabled,
                configured_summarize=benchmark_config.summarize,
                configured_limits=benchmark_config.limits,
                max_reprompts=benchmark_config.max_reprompts,
                enabled_capabilities=enabled_capabilities,
                solutions_folder=solutions_folder,
                extra_prompt=extra_prompt,
            )
        )
    return challenges


app = typer.Typer(
    no_args_is_help=True,
    help="Build and run the Challenge 6.1 Android vulnerability benchmark.",
)


@app.callback()
def callback() -> None:
    """Load local environment variables before running a command."""
    load_dotenv()
    configure_logging(default_level="INFO")


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
        help="Benchmark configuration file (TOML or JSON).",
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
    notes: str | None = typer.Option(
        None,
        "--notes",
        help="Optional notes describing this benchmark run (saved to NOTES.md).",
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
    notes_val = _unwrap(notes)

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
    (results / "challenge.toml").write_text(benchmark_config.formatted_toml())
    if notes_val is not None and str(notes_val).strip():
        (results / "NOTES.md").write_text(str(notes_val).strip() + "\n", encoding="utf-8")

    dated_name = format_dated_name(benchmark_config.name)

    selected_definitions = tuple(select_challenges(benchmark_config.challenges))
    challenges: list[Challenge] = _build_challenges_for_config(
        benchmark_config, selected_definitions
    )
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
    all_challenges: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Resume all challenges (alias for setting default mode to auto).",
    ),
    mode: ResumeMode | None = typer.Option(
        None,
        "--mode",
        "-m",
        help="Default resume mode: auto, regrade, last-attempt, keep-going, none.",
    ),
    attempts: int | None = typer.Option(
        None,
        "--attempts",
        help="Default additional attempts (defaults to challenge.toml max_reprompts).",
    ),
    challenge: list[str] | None = typer.Option(
        None,
        "--challenge",
        "-c",
        help="Per-challenge spec: 'name[,mode=<mode>][,attempts=<attempts>]' (repeatable).",
    ),
    results_opt: Path | None = typer.Option(
        None,
        "--results",
        file_okay=False,
        resolve_path=True,
        help="Results directory (alternative to positional argument).",
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
    notes: str | None = typer.Option(
        None,
        "--notes",
        help="Optional notes to save or append to NOTES.md in results directory.",
    ),
) -> None:
    """Resume an existing benchmark run."""
    res = _unwrap(results)
    res_opt = _unwrap(results_opt)
    notes_val = _unwrap(notes)
    target_results: Path | None = res or res_opt
    if target_results is None:
        raise typer.BadParameter("results directory must be provided", param_hint="results")

    if not target_results.exists() or not target_results.is_dir():
        raise typer.BadParameter(
            f"results directory {target_results} must exist", param_hint="results"
        )

    if notes_val is not None and str(notes_val).strip():
        notes_path = target_results / "NOTES.md"
        if notes_path.is_file():
            existing = notes_path.read_text(encoding="utf-8").rstrip()
            notes_path.write_text(f"{existing}\n\n## Resume Notes\n{str(notes_val).strip()}\n", encoding="utf-8")
        else:
            notes_path.write_text(str(notes_val).strip() + "\n", encoding="utf-8")

    if (target_results / "challenge.toml").is_file():
        config_file = target_results / "challenge.toml"
    elif (target_results / "challenge.json").is_file():
        config_file = target_results / "challenge.json"
    else:
        raise typer.BadParameter(
            f"challenge.toml not found in {target_results}", param_hint="results"
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

    # Determine default attempts
    att_val = _unwrap(attempts)
    if att_val is not None:
        default_attempts = att_val
    else:
        default_attempts = benchmark_config.max_reprompts if benchmark_config.max_reprompts is not None else 1
    if default_attempts < 0:
        default_attempts = 1

    # Determine default mode
    raw_challenges = _unwrap(challenge) or []
    mode_val = _unwrap(mode)
    all_ch = bool(_unwrap(all_challenges))
    if mode_val is not None:
        default_mode = mode_val
    elif all_ch:
        default_mode = ResumeMode.AUTO
    elif raw_challenges:
        default_mode = ResumeMode.NONE
    else:
        default_mode = ResumeMode.AUTO

    selected_definitions = tuple(select_challenges(benchmark_config.challenges))
    all_challenge_names = [d.name.value for d in selected_definitions]

    resume_configs: dict[str, ChallengeResumeConfig] = {
        name: ChallengeResumeConfig(
            challenge=name,
            mode=default_mode,
            attempts=default_attempts,
        )
        for name in all_challenge_names
    }

    # Apply per-challenge overrides
    for spec in raw_challenges:
        ch_default_mode = ResumeMode.AUTO if default_mode == ResumeMode.NONE else default_mode
        try:
            parsed_cfg = ChallengeResumeConfig.parse(
                spec,
                default_mode=ch_default_mode,
                default_attempts=default_attempts,
            )
            resume_configs[parsed_cfg.challenge] = parsed_cfg
        except ValueError as exc:
            raise typer.BadParameter(str(exc), param_hint="--challenge")

    # Validate attempts=0 only for regrade
    for name, cfg in resume_configs.items():
        if cfg.mode != ResumeMode.NONE and cfg.attempts == 0 and cfg.mode != ResumeMode.REGRADE:
            raise typer.BadParameter(
                f"attempts=0 is only allowed when mode is 'regrade' (challenge '{name}' has mode '{cfg.mode.value}')",
                param_hint="--attempts",
            )

    challenges_built: list[Challenge] = _build_challenges_for_config(
        benchmark_config, selected_definitions
    )
    dated_name = format_dated_name(benchmark_config.name)
    benchmark_run = BenchmarkRun(
        name=dated_name,
        num_instances=benchmark_config.num_instances,
        challenges=challenges_built,
        output_folder=target_results,
    )
    benchmark_result = resume_benchmark(
        benchmark_run,
        benchmark_config=benchmark_config,
        resume_configs=resume_configs,
    )
    typer.echo(benchmark_result.model_dump_json(indent=2))


@app.command("grader")
@app.command("test-grader", hidden=True)
def grader_command(
    results: Path = typer.Argument(
        None,
        file_okay=False,
        resolve_path=True,
        help="Results directory containing challenge solutions to grade.",
    ),
    challenges: list[str] = typer.Argument(
        None,
        help="Challenge names to grade (optional positional arguments).",
    ),
    results_opt: Path | None = typer.Option(
        None,
        "--results",
        file_okay=False,
        resolve_path=True,
        help="Results directory (alternative to positional argument).",
    ),
    challenge_opt: list[str] | None = typer.Option(
        None,
        "--challenge",
        "-c",
        help="Challenge name(s) to grade (alternative/repeatable flag).",
    ),
    all_challenges: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Grade all challenges in the results directory.",
    ),
) -> None:
    """Run read-only capability grading on challenge solutions."""
    res = _unwrap(results)
    res_opt = _unwrap(results_opt)
    target_results: Path | None = res or res_opt
    if target_results is None:
        raise typer.BadParameter("results directory must be provided", param_hint="results")

    if not target_results.exists() or not target_results.is_dir():
        raise typer.BadParameter(
            f"results directory {target_results} must exist", param_hint="results"
        )

    if (target_results / "challenge.toml").is_file():
        config_file = target_results / "challenge.toml"
    elif (target_results / "challenge.json").is_file():
        config_file = target_results / "challenge.json"
    else:
        raise typer.BadParameter(
            f"challenge.toml not found in {target_results}", param_hint="results"
        )

    benchmark_config = BenchmarkConfig.from_file(config_file)

    specified_names: set[str] = set()
    raw_challenges = _unwrap(challenges) or []
    if raw_challenges:
        specified_names.update(raw_challenges)
    raw_opts = _unwrap(challenge_opt) or []
    if raw_opts:
        for opt in raw_opts:
            specified_names.update([p.strip() for p in opt.split(",") if p.strip()])

    all_ch = bool(_unwrap(all_challenges))
    if not all_ch and not specified_names:
        raise typer.BadParameter(
            "Specify challenge names to grade or use --all.",
            param_hint="challenges",
        )

    if all_ch:
        selected_definitions = tuple(
            defn
            for defn in select_challenges(benchmark_config.challenges)
            if (target_results / defn.name.value).is_dir()
        )
    else:
        selected_definitions = tuple(
            defn
            for defn in select_challenges(benchmark_config.challenges)
            if defn.name.value in specified_names and (target_results / defn.name.value).is_dir()
        )

    if not selected_definitions:
        raise typer.BadParameter(
            f"no challenge solution directories found in {target_results} for specified challenges",
            param_hint="results",
        )

    challenges_built: list[Challenge] = _build_challenges_for_config(
        benchmark_config, selected_definitions
    )
    dated_name = format_dated_name(benchmark_config.name)
    benchmark_run = BenchmarkRun(
        name=dated_name,
        num_instances=benchmark_config.num_instances,
        challenges=challenges_built,
        output_folder=target_results,
    )
    grader_result = run_test_grader(benchmark_run)
    typer.echo(grader_result.model_dump_json(indent=2))


test_grader_command = grader_command
grader_command.__test__ = False  # type: ignore[attr-defined]
test_grader_command.__test__ = False  # type: ignore[attr-defined]


@app.command("web")
def web_command(
    results: Path = typer.Option(
        ...,
        "--results",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Directory containing benchmark results to monitor.",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="Host to bind the web server (default: 127.0.0.1).",
    ),
    port: int = typer.Option(
        8080,
        "--port",
        help="Port to bind the web server (default: 8080).",
    ),
) -> None:
    """Start the web viewer dashboard for android-bench results."""
    from android_bench.web.server import run_server

    target_results = _unwrap(results)
    if target_results is None:
        raise typer.BadParameter("results directory must be provided", param_hint="--results")
    if not target_results.exists():
        raise typer.BadParameter(f"results directory {target_results} does not exist", param_hint="--results")

    run_server(results_dir=target_results, host=host, port=port)


def main() -> None:
    app()
