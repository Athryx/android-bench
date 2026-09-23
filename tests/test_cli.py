from pathlib import Path
from unittest.mock import patch

from android_bench.catalog import CHALLENGES
from android_bench.cli import callback, run_command


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


def test_run_command_test_grader_filters_challenges_and_dispatches(tmp_path: Path) -> None:
    import typer
    import pytest

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
        patch("android_bench.cli.run_benchmark") as run_benchmark_mock,
    ):
        run_command(config, results_dir, test_grader=True)

    run_benchmark_mock.assert_not_called()
    run_test_grader_mock.assert_called_once()
    run_arg = run_test_grader_mock.call_args.args[0]
    assert len(run_arg.challenges) == 1
    assert run_arg.challenges[0].name == first_ch


def test_run_command_test_grader_validates_results_dir(tmp_path: Path) -> None:
    import typer
    import pytest

    config = tmp_path / "benchmark.json"
    config.write_text(
        '{"name": "test", "harness": "codex", "model_config": {"model": "gpt-6-astra"}}'
    )

    non_existent = tmp_path / "does_not_exist"
    with pytest.raises(typer.BadParameter, match="results directory must exist"):
        run_command(config, non_existent, test_grader=True)

    empty_dir = tmp_path / "empty_results"
    empty_dir.mkdir()
    with pytest.raises(typer.BadParameter, match="no challenge solution directories found"):
        run_command(config, empty_dir, test_grader=True)


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

    with pytest.raises(typer.BadParameter, match="results directory must be empty"):
        run_command(config, non_empty, test_grader=False)


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




