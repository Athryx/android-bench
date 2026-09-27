from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from android_bench.catalog import CHALLENGES
from android_bench.cli import (
    callback,
    format_dated_name,
    resume_command,
    run_command,
    test_grader_command,
)



def test_callback_loads_dotenv() -> None:
    with patch("android_bench.cli.load_dotenv") as load_dotenv:
        callback()

    load_dotenv.assert_called_once_with()


def test_run_applies_global_internet_setting_to_every_challenge(
    tmp_path: Path,
) -> None:
    config = tmp_path / "benchmark.json"
    config.write_text(
        """{
          "name": "internet-smoke",
          "num_instances": 1,
          "harness": "codex",
          "internet_enabled": true,
          "summarize": true,
          "model_config": {"model": "gpt-6-astra"}
        }"""
    )
    benchmark_result = type(
        "BenchmarkResultStub",
        (),
        {"model_dump_json": lambda self, indent: "{}"},
    )()

    with (
        patch("android_bench.cli.select_challenges", return_value=CHALLENGES[:2]),
        patch(
            "android_bench.cli.run_benchmark", return_value=benchmark_result
        ) as run_benchmark,
    ):
        run_command(config, tmp_path / "results")

    run = run_benchmark.call_args.args[0]
    assert len(run.challenges) == 2
    assert all(challenge.internet_enabled for challenge in run.challenges)
    assert all(challenge.summarize for challenge in run.challenges)


def test_test_grader_command_filters_challenges_and_dispatches(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    # Write challenge.json directly inside results_dir
    (results_dir / "challenge.json").write_text(
        """{
          "name": "test-grader-smoke",
          "num_instances": 1,
          "harness": "codex",
          "model_config": {"model": "gpt-6-astra"}
        }"""
    )
    # Create folder for only the first challenge
    first_ch = CHALLENGES[0].name.value
    (results_dir / first_ch).mkdir()

    stub_result = type(
        "TestGraderResultStub",
        (),
        {"model_dump_json": lambda self, indent: '{"status": "ok"}'},
    )()

    with (
        patch("android_bench.cli.select_challenges", return_value=CHALLENGES[:3]),
        patch(
            "android_bench.cli.run_test_grader", return_value=stub_result
        ) as run_test_grader_mock,
    ):
        test_grader_command(results_dir)

    run_test_grader_mock.assert_called_once()
    run_arg = run_test_grader_mock.call_args.args[0]
    assert len(run_arg.challenges) == 1
    assert run_arg.challenges[0].name == first_ch


def test_test_grader_command_with_explicit_config(tmp_path: Path) -> None:
    config = tmp_path / "benchmark.json"
    config.write_text(
        """{
          "name": "test-grader-smoke",
          "num_instances": 1,
          "harness": "codex",
          "model_config": {"model": "gpt-6-astra"}
        }"""
    )
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    first_ch = CHALLENGES[0].name.value
    (results_dir / first_ch).mkdir()

    stub_result = type(
        "TestGraderResultStub",
        (),
        {"model_dump_json": lambda self, indent: '{"status": "ok"}'},
    )()

    with (
        patch("android_bench.cli.select_challenges", return_value=CHALLENGES[:3]),
        patch(
            "android_bench.cli.run_test_grader", return_value=stub_result
        ) as run_test_grader_mock,
    ):
        test_grader_command(results_dir, config=config)

    run_test_grader_mock.assert_called_once()


def test_test_grader_command_validates_results_dir(tmp_path: Path) -> None:
    import typer
    import pytest

    non_existent = tmp_path / "does_not_exist"
    with pytest.raises(typer.BadParameter, match="results directory .* must exist"):
        test_grader_command(non_existent)

    empty_dir = tmp_path / "empty_results"
    empty_dir.mkdir()
    with pytest.raises(typer.BadParameter, match="challenge.toml not found"):
        test_grader_command(empty_dir)

    (empty_dir / "challenge.json").write_text(
        '{"name": "test", "harness": "codex", "model_config": {"model": "gpt-6-astra"}}'
    )
    with pytest.raises(typer.BadParameter, match="no challenge solution directories found"):
        test_grader_command(empty_dir)


def test_run_command_writes_challenge_toml(tmp_path: Path) -> None:
    config = tmp_path / "benchmark.toml"
    config.write_text(
        """
        name = "write-config-smoke"
        num_instances = 1
        harness = "codex"
        [model_config]
        model = "gpt-6-astra"
        """
    )
    results_dir = tmp_path / "results"
    stub_result = type(
        "BenchmarkResultStub",
        (),
        {"model_dump_json": lambda self, indent: "{}"},
    )()

    with (
        patch("android_bench.cli.select_challenges", return_value=CHALLENGES[:1]),
        patch("android_bench.cli.run_benchmark", return_value=stub_result),
    ):
        run_command(config, results_dir)

    assert (results_dir / "challenge.toml").is_file()
    assert "write-config-smoke" in (results_dir / "challenge.toml").read_text()


def test_run_command_standard_run_rejects_non_empty_results(tmp_path: Path) -> None:
    import typer
    import pytest

    config = tmp_path / "benchmark.json"
    config.write_text(
        '{"name": "test", "harness": "codex", "model_config": {"model": "gpt-6-astra"}}'
    )

    non_empty = tmp_path / "non_empty"
    non_empty.mkdir()
    (non_empty / "some_file.txt").write_text("hello")

    with pytest.raises(typer.BadParameter, match="results directory .* must be empty"):
        run_command(config, non_empty)


def test_setup_command() -> None:
    from android_bench.cli import setup

    with patch("android_bench.cli.setup_images") as mock_setup_images:
        setup()
        mock_setup_images.assert_called_once()


def test_run_command_applies_cli_limits_override(tmp_path: Path) -> None:
    from decimal import Decimal

    config = tmp_path / "benchmark.json"
    config.write_text(
        """{
          "name": "cli-limits-test",
          "num_instances": 1,
          "harness": "codex",
          "model_config": {"model": "gpt-6-astra"},
          "limits": {
            "token_limit": 5000,
            "turn_limit": 2
          }
        }"""
    )
    benchmark_result = type(
        "BenchmarkResultStub",
        (),
        {"model_dump_json": lambda self, indent: "{}"},
    )()

    with (
        patch("android_bench.cli.select_challenges", return_value=CHALLENGES[:1]),
        patch(
            "android_bench.cli.run_benchmark", return_value=benchmark_result
        ) as run_benchmark_mock,
    ):
        run_command(
            config,
            tmp_path / "results",
            token_limit=15000,
            time_limit=300.0,
            dollar_limit=2.5,
        )

    run = run_benchmark_mock.call_args.args[0]
    challenge = run.challenges[0]
    assert challenge.limits is not None
    assert challenge.limits.token_limit == 15000
    assert challenge.limits.turn_limit == 2  # preserved from config
    assert challenge.limits.time_limit == 300.0  # overridden from CLI
    assert challenge.limits.dollar_limit == Decimal("2.5")  # overridden from CLI


def test_cli_runner_with_limits_flags(tmp_path: Path) -> None:
    from decimal import Decimal
    from typer.testing import CliRunner
    from android_bench.cli import app

    config = tmp_path / "benchmark.json"
    config.write_text(
        """{
          "name": "cli-flags-test",
          "num_instances": 1,
          "harness": "codex",
          "model_config": {"model": "gpt-6-astra"}
        }"""
    )
    results = tmp_path / "results"

    benchmark_result = type(
        "BenchmarkResultStub",
        (),
        {"model_dump_json": lambda self, indent: "{}"},
    )()

    with (
        patch("android_bench.cli.select_challenges", return_value=CHALLENGES[:1]),
        patch(
            "android_bench.cli.run_benchmark", return_value=benchmark_result
        ) as run_benchmark_mock,
    ):
        runner = CliRunner()
        res = runner.invoke(
            app,
            [
                "run",
                "--config",
                str(config),
                "--results",
                str(results),
                "--token-limit",
                "10000",
                "--turn-limit",
                "8",
                "--timeout",
                "120",
                "--dollar-limit",
                "3.5",
            ],
        )

    assert res.exit_code == 0
    run = run_benchmark_mock.call_args.args[0]
    challenge = run.challenges[0]
    assert challenge.limits is not None
    assert challenge.limits.token_limit == 10000
    assert challenge.limits.turn_limit == 8
    assert challenge.limits.time_limit == 120.0
    assert challenge.limits.dollar_limit == Decimal("3.5")


def test_run_command_rejects_test_grader_flag(tmp_path: Path) -> None:
    from typer.testing import CliRunner
    from android_bench.cli import app

    config = tmp_path / "benchmark.json"
    config.write_text(
        '{"name": "reject-test", "harness": "codex", "model_config": {"model": "gpt-6-astra"}}'
    )
    results = tmp_path / "results"

    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "run",
            "--config",
            str(config),
            "--results",
            str(results),
            "--test-grader",
        ],
    )
    assert res.exit_code != 0
    assert "No such option: --test-grader" in res.output or "Error" in res.output


def test_resume_cli_uses_challenge_json(tmp_path: Path) -> None:
    from typer.testing import CliRunner
    from android_bench.cli import app

    results = tmp_path / "results"
    results.mkdir()
    (results / "challenge.json").write_text(
        """{
          "name": "resume-cli-test",
          "num_instances": 1,
          "harness": "codex",
          "model_config": {"model": "gpt-6-astra"}
        }"""
    )

    stub_result = type(
        "BenchmarkResultStub",
        (),
        {"model_dump_json": lambda self, indent: "{}"},
    )()

    with (
        patch("android_bench.cli.select_challenges", return_value=CHALLENGES[:1]),
        patch(
            "android_bench.cli.resume_benchmark", return_value=stub_result
        ) as resume_benchmark_mock,
    ):
        runner = CliRunner()
        res = runner.invoke(app, ["resume", str(results)])

    assert res.exit_code == 0
    resume_benchmark_mock.assert_called_once()
    run = resume_benchmark_mock.call_args.args[0]
    assert run.output_folder == results


def test_resume_cli_with_explicit_config_and_limits(tmp_path: Path) -> None:
    from decimal import Decimal
    from typer.testing import CliRunner
    from android_bench.cli import app

    config = tmp_path / "benchmark.json"
    config.write_text(
        """{
          "name": "resume-limits-test",
          "num_instances": 1,
          "harness": "codex",
          "model_config": {"model": "gpt-6-astra"}
        }"""
    )
    results = tmp_path / "results"
    results.mkdir()

    stub_result = type(
        "BenchmarkResultStub",
        (),
        {"model_dump_json": lambda self, indent: "{}"},
    )()

    with (
        patch("android_bench.cli.select_challenges", return_value=CHALLENGES[:1]),
        patch(
            "android_bench.cli.resume_benchmark", return_value=stub_result
        ) as resume_benchmark_mock,
    ):
        runner = CliRunner()
        res = runner.invoke(
            app,
            [
                "resume",
                str(results),
                "--config",
                str(config),
                "--token-limit",
                "20000",
                "--dollar-limit",
                "4.5",
            ],
        )

    assert res.exit_code == 0
    run = resume_benchmark_mock.call_args.args[0]
    challenge = run.challenges[0]
    assert challenge.limits is not None
    assert challenge.limits.token_limit == 20000
    assert challenge.limits.dollar_limit == Decimal("4.5")


def test_format_dated_name_includes_time_to_minute() -> None:
    dt = datetime(2026, 9, 27, 13, 46, tzinfo=timezone.utc)
    formatted = format_dated_name("run1", dt)
    assert formatted == "run1 (September 27, 2026, 13:46)"


def test_run_command_names_run_with_date_and_time_to_minute(tmp_path: Path) -> None:
    import re

    config = tmp_path / "benchmark.json"
    config.write_text(
        """{
          "name": "time-smoke",
          "num_instances": 1,
          "harness": "codex",
          "model_config": {"model": "gpt-6-astra"}
        }"""
    )
    benchmark_result = type(
        "BenchmarkResultStub",
        (),
        {"model_dump_json": lambda self, indent: "{}"},
    )()

    with (
        patch("android_bench.cli.select_challenges", return_value=CHALLENGES[:1]),
        patch(
            "android_bench.cli.run_benchmark", return_value=benchmark_result
        ) as run_benchmark_mock,
    ):
        run_command(config, tmp_path / "results")

    run = run_benchmark_mock.call_args.args[0]
    # Check that the run name matches: <name> (<Month> <day>, <year>, <HH:MM>)
    pattern = r"^time-smoke \([A-Z][a-z]+ \d{1,2}, \d{4}, \d{2}:\d{2}\)$"
    assert re.match(pattern, run.name) is not None





