from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from android_bench.catalog import load_catalog
from android_bench.cli import (
    callback,
    format_dated_name,
    resume_command,
    run_command,
    test_grader_command,
    web_command,
)

CHALLENGES = load_catalog().defaults


def test_callback_loads_dotenv() -> None:
    with (
        patch("android_bench.cli.load_dotenv") as load_dotenv,
        patch("android_bench.cli.configure_logging") as configure_logging,
    ):
        callback()

    load_dotenv.assert_called_once_with()
    configure_logging.assert_called_once_with(default_level="INFO")


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
        patch("android_bench.cli._select_definitions", return_value=CHALLENGES[:2]),
        patch(
            "android_bench.cli.run_benchmark", return_value=benchmark_result
        ) as run_benchmark,
    ):
        run_command(config=config, results=tmp_path / "results")

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
    first_ch = CHALLENGES[0].name
    (results_dir / first_ch).mkdir()

    stub_result = type(
        "TestGraderResultStub",
        (),
        {"model_dump_json": lambda self, indent: '{"status": "ok"}'},
    )()

    with (
        patch("android_bench.cli._select_definitions", return_value=CHALLENGES[:3]),
        patch(
            "android_bench.cli.run_test_grader", return_value=stub_result
        ) as run_test_grader_mock,
    ):
        test_grader_command(results=results_dir, all_challenges=True)

    run_test_grader_mock.assert_called_once()
    run_arg = run_test_grader_mock.call_args.args[0]
    assert len(run_arg.challenges) == 1
    assert run_arg.challenges[0].name == first_ch


def test_test_grader_command_with_explicit_challenges(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    (results_dir / "challenge.json").write_text(
        """{
          "name": "test-grader-smoke",
          "num_instances": 1,
          "harness": "codex",
          "model_config": {"model": "gpt-6-astra"}
        }"""
    )
    first_ch = CHALLENGES[0].name
    (results_dir / first_ch).mkdir()

    stub_result = type(
        "TestGraderResultStub",
        (),
        {"model_dump_json": lambda self, indent: '{"status": "ok"}'},
    )()

    with (
        patch("android_bench.cli._select_definitions", return_value=CHALLENGES[:3]),
        patch(
            "android_bench.cli.run_test_grader", return_value=stub_result
        ) as run_test_grader_mock,
    ):
        test_grader_command(results=results_dir, challenges=[first_ch])

    run_test_grader_mock.assert_called_once()
    run_arg = run_test_grader_mock.call_args.args[0]
    assert len(run_arg.challenges) == 1
    assert run_arg.challenges[0].name == first_ch


def test_test_grader_command_validates_results_dir(tmp_path: Path) -> None:
    import typer
    import pytest

    non_existent = tmp_path / "does_not_exist"
    with pytest.raises(typer.BadParameter, match="results directory .* must exist"):
        test_grader_command(results=non_existent)

    empty_dir = tmp_path / "empty_results"
    empty_dir.mkdir()
    with pytest.raises(typer.BadParameter, match="challenge.toml not found"):
        test_grader_command(results=empty_dir)

    (empty_dir / "challenge.json").write_text(
        '{"name": "test", "harness": "codex", "model_config": {"model": "gpt-6-astra"}}'
    )
    with pytest.raises(typer.BadParameter, match="Specify challenge names to grade or use --all"):
        test_grader_command(results=empty_dir)

    with pytest.raises(typer.BadParameter, match="no challenge solution directories found"):
        test_grader_command(results=empty_dir, all_challenges=True)


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
        patch("android_bench.cli._select_definitions", return_value=CHALLENGES[:1]),
        patch("android_bench.cli.run_benchmark", return_value=stub_result),
    ):
        run_command(config=config, results=results_dir)

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
        run_command(config=config, results=non_empty)


def test_setup_command() -> None:
    from android_bench.cli import setup

    with patch("android_bench.cli.setup_images") as mock_setup_images:
        setup()
        mock_setup_images.assert_called_once_with(load_catalog().definitions)


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
        patch("android_bench.cli._select_definitions", return_value=CHALLENGES[:1]),
        patch(
            "android_bench.cli.run_benchmark", return_value=benchmark_result
        ) as run_benchmark_mock,
    ):
        run_command(
            config=config,
            results=tmp_path / "results",
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
        patch("android_bench.cli._select_definitions", return_value=CHALLENGES[:1]),
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
        patch("android_bench.cli._select_definitions", return_value=CHALLENGES[:1]),
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


def test_resume_cli_with_limits(tmp_path: Path) -> None:
    from decimal import Decimal
    from typer.testing import CliRunner
    from android_bench.cli import app

    results = tmp_path / "results"
    results.mkdir()
    (results / "challenge.json").write_text(
        """{
          "name": "resume-limits-test",
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
        patch("android_bench.cli._select_definitions", return_value=CHALLENGES[:1]),
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


def test_resume_cli_challenge_spec_and_modes(tmp_path: Path) -> None:
    from typer.testing import CliRunner
    from android_bench.cli import app
    from android_bench.models import ResumeMode

    results = tmp_path / "results"
    results.mkdir()
    (results / "challenge.json").write_text(
        """{
          "name": "resume-spec-test",
          "num_instances": 1,
          "harness": "codex",
          "max_reprompts": 3,
          "model_config": {"model": "gpt-6-astra"}
        }"""
    )

    stub_result = type(
        "BenchmarkResultStub",
        (),
        {"model_dump_json": lambda self, indent: "{}"},
    )()

    with (
        patch("android_bench.cli._select_definitions", return_value=CHALLENGES[:3]),
        patch(
            "android_bench.cli.resume_benchmark", return_value=stub_result
        ) as resume_benchmark_mock,
    ):
        runner = CliRunner()
        first_ch = CHALLENGES[0].name
        second_ch = CHALLENGES[1].name
        res = runner.invoke(
            app,
            [
                "resume",
                str(results),
                "--challenge",
                f"{first_ch},mode=regrade,attempts=0",
                "--challenge",
                f"{second_ch},mode=keep-going,attempts=2",
            ],
        )

    assert res.exit_code == 0
    resume_benchmark_mock.assert_called_once()
    kwargs = resume_benchmark_mock.call_args.kwargs
    resume_configs = kwargs["resume_configs"]
    assert resume_configs[first_ch].mode == ResumeMode.REGRADE
    assert resume_configs[first_ch].attempts == 0
    assert resume_configs[second_ch].mode == ResumeMode.KEEP_GOING
    assert resume_configs[second_ch].attempts == 2
    # Unmentioned 3rd challenge should have mode == NONE
    third_ch = CHALLENGES[2].name
    assert resume_configs[third_ch].mode == ResumeMode.NONE


def test_resume_cli_all_with_exclusion(tmp_path: Path) -> None:
    from typer.testing import CliRunner
    from android_bench.cli import app
    from android_bench.models import ResumeMode

    results = tmp_path / "results"
    results.mkdir()
    (results / "challenge.json").write_text(
        """{
          "name": "resume-exclusion-test",
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
        patch("android_bench.cli._select_definitions", return_value=CHALLENGES[:2]),
        patch(
            "android_bench.cli.resume_benchmark", return_value=stub_result
        ) as resume_benchmark_mock,
    ):
        runner = CliRunner()
        first_ch = CHALLENGES[0].name
        second_ch = CHALLENGES[1].name
        res = runner.invoke(
            app,
            [
                "resume",
                str(results),
                "--all",
                "--challenge",
                f"{first_ch},mode=none",
            ],
        )

    assert res.exit_code == 0
    resume_benchmark_mock.assert_called_once()
    resume_configs = resume_benchmark_mock.call_args.kwargs["resume_configs"]
    assert resume_configs[first_ch].mode == ResumeMode.NONE
    assert resume_configs[second_ch].mode == ResumeMode.AUTO


def test_resume_cli_rejects_zero_attempts_on_non_regrade(tmp_path: Path) -> None:
    from typer.testing import CliRunner
    from android_bench.cli import app

    results = tmp_path / "results"
    results.mkdir()
    (results / "challenge.json").write_text(
        """{
          "name": "resume-reject-test",
          "num_instances": 1,
          "harness": "codex",
          "model_config": {"model": "gpt-6-astra"}
        }"""
    )

    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "resume",
            str(results),
            "--challenge",
            f"{CHALLENGES[0].name},mode=keep-going,attempts=0",
        ],
    )
    assert res.exit_code != 0
    assert "attempts=0 is only allowed" in res.output
    assert "regrade" in res.output


def test_grader_cli_subcommand(tmp_path: Path) -> None:
    from typer.testing import CliRunner
    from android_bench.cli import app

    results = tmp_path / "results"
    results.mkdir()
    (results / "challenge.json").write_text(
        """{
          "name": "grader-cli-test",
          "num_instances": 1,
          "harness": "codex",
          "model_config": {"model": "gpt-6-astra"}
        }"""
    )
    first_ch = CHALLENGES[0].name
    (results / first_ch).mkdir()

    stub_result = type(
        "TestGraderResultStub",
        (),
        {"model_dump_json": lambda self, indent: '{"score": 1.0}'},
    )()

    with (
        patch("android_bench.cli._select_definitions", return_value=CHALLENGES[:1]),
        patch("android_bench.cli.run_test_grader", return_value=stub_result) as run_grader_mock,
    ):
        runner = CliRunner()
        res = runner.invoke(app, ["grader", str(results), first_ch])

    assert res.exit_code == 0
    run_grader_mock.assert_called_once()
    run = run_grader_mock.call_args.args[0]
    assert len(run.challenges) == 1
    assert run.challenges[0].name == first_ch


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
        patch("android_bench.cli._select_definitions", return_value=CHALLENGES[:1]),
        patch(
            "android_bench.cli.run_benchmark", return_value=benchmark_result
        ) as run_benchmark_mock,
    ):
        run_command(config=config, results=tmp_path / "results")

    run = run_benchmark_mock.call_args.args[0]
    # Check that the run name matches: <name> (<Month> <day>, <year>, <HH:MM>)
    pattern = r"^time-smoke \([A-Z][a-z]+ \d{1,2}, \d{4}, \d{2}:\d{2}\)$"
    assert re.match(pattern, run.name) is not None


def test_cli_builds_challenges_with_custom_overrides(tmp_path: Path) -> None:
    from android_bench.cli import _build_challenges_for_config
    CHALLENGE_BY_NAME = load_catalog().by_name
    from android_bench.config import BenchmarkConfig
    from android_bench.models import Capability

    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    config = BenchmarkConfig.model_validate(
        {
            "name": "custom-cli-run",
            "harness": "codex",
            "model_config": {"model": "gpt-6-astra"},
            "challenges": [
                {
                    "name": "element",
                    "capabilities": ["code_execution"],
                    "solutions_folder": str(seed_dir),
                    "extra_prompt": "Element extra prompt",
                },
                "vlc",
            ],
        }
    )

    definitions = (
        CHALLENGE_BY_NAME["element"],
        CHALLENGE_BY_NAME["vlc"],
    )
    challenges = _build_challenges_for_config(config, definitions)
    assert len(challenges) == 2

    # element challenge
    ch0 = challenges[0]
    assert ch0.name == "element"
    assert ch0.enabled_capabilities == (Capability.CODE_EXECUTION,)
    assert ch0.solutions_folder == seed_dir
    assert ch0.extra_prompt == "Element extra prompt"

    # vlc challenge (default)
    ch1 = challenges[1]
    assert ch1.name == "vlc"
    assert ch1.enabled_capabilities == CHALLENGE_BY_NAME["vlc"].enabled_capabilities
    assert ch1.solutions_folder is None
    assert ch1.extra_prompt is None


def test_run_command_writes_notes(tmp_path: Path) -> None:
    config = tmp_path / "benchmark.json"
    config.write_text(
        """{
          "name": "notes-smoke",
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
    results_dir = tmp_path / "results_notes"

    with (
        patch("android_bench.cli._select_definitions", return_value=CHALLENGES[:1]),
        patch("android_bench.cli.run_benchmark", return_value=benchmark_result),
    ):
        run_command(config=config, results=results_dir, notes="Investigating privilege escalation")

    assert (results_dir / "NOTES.md").is_file()
    assert "Investigating privilege escalation" in (results_dir / "NOTES.md").read_text(encoding="utf-8")


def test_resume_command_appends_notes(tmp_path: Path) -> None:
    results_dir = tmp_path / "results_resume"
    results_dir.mkdir()
    (results_dir / "challenge.toml").write_text(
        """name = "resumed_run"
harness = "codex"
[model_config]
model = "gpt-6-astra"
"""
    )
    (results_dir / "NOTES.md").write_text("Initial notes.\n")

    benchmark_result = type(
        "BenchmarkResultStub",
        (),
        {"model_dump_json": lambda self, indent: "{}"},
    )()

    with (
        patch("android_bench.cli._select_definitions", return_value=CHALLENGES[:1]),
        patch("android_bench.cli.resume_benchmark", return_value=benchmark_result),
    ):
        resume_command(results=results_dir, notes="Resuming after timeout fix")

    content = (results_dir / "NOTES.md").read_text(encoding="utf-8")
    assert "Initial notes." in content
    assert "Resume Notes" in content
    assert "Resuming after timeout fix" in content


def test_custom_catalog_run_snapshots_definitions_for_resume_and_grader(tmp_path: Path) -> None:
    from typer.testing import CliRunner
    from android_bench.cli import app

    catalog = tmp_path / "custom-catalog"
    catalog.mkdir()
    definition = catalog / "custom.toml"
    definition.write_text(
        'name = "custom_app"\nartifact = "apps/custom.apk"\npackage = "com.custom"\n'
        'enabled_capabilities = ["file_write"]\ninstall_app = true\n'
    )
    config = tmp_path / "benchmark.toml"
    config.write_text(
        'name = "custom-run"\nchallenges = ["custom_app"]\nharness = "codex"\n'
        '[model_config]\nmodel = "gpt-6-astra"\n'
    )
    results = tmp_path / "results"
    stub_result = type("ResultStub", (), {"model_dump_json": lambda self, indent: "{}"})()
    runner = CliRunner()

    with patch("android_bench.cli.run_benchmark", return_value=stub_result) as run:
        result = runner.invoke(
            app, ["run", "--catalog", str(catalog), "--config", str(config), "--results", str(results)]
        )
    assert result.exit_code == 0, result.output
    assert run.call_args.args[0].challenges[0].name == "custom_app"
    snapshot = load_catalog(results / "catalog")
    assert snapshot.by_name["custom_app"].artifact == catalog / "apps/custom.apk"

    # Neither resume nor grading should need the original catalog definitions.
    definition.unlink()
    with patch("android_bench.cli.resume_benchmark", return_value=stub_result) as resume:
        result = runner.invoke(app, ["resume", str(results)])
    assert result.exit_code == 0, result.output
    assert resume.call_args.args[0].challenges[0].name == "custom_app"

    (results / "custom_app").mkdir()
    with patch("android_bench.cli.run_test_grader", return_value=stub_result) as grade:
        result = runner.invoke(app, ["grader", str(results), "custom_app"])
    assert result.exit_code == 0, result.output
    assert grade.call_args.args[0].challenges[0].name == "custom_app"


@pytest.mark.parametrize("command", ["setup", "run", "resume", "grader"])
def test_cli_commands_advertise_catalog_option(command: str) -> None:
    from typer.testing import CliRunner
    from android_bench.cli import app

    result = CliRunner().invoke(app, [command, "--help"])
    assert result.exit_code == 0
    assert "--catalog" in result.output


def test_select_definitions_explicit_catalog_overrides_snapshot(tmp_path: Path) -> None:
    from android_bench.cli import _save_catalog, _select_definitions
    from android_bench.config import BenchmarkConfig

    results = tmp_path / "results"
    results.mkdir()
    _save_catalog(results, CHALLENGES[:1])
    config = BenchmarkConfig.model_validate(
        {"name": "selection", "harness": "codex", "model_config": {"model": "gpt-6-astra"}}
    )
    assert _select_definitions(config, None, results) == CHALLENGES[:1]
    assert _select_definitions(config, None) == CHALLENGES
    assert _select_definitions(config, Path("challenges"), results) == CHALLENGES


def test_setup_uses_custom_catalog(tmp_path: Path) -> None:
    from typer.testing import CliRunner
    from android_bench.cli import app

    (tmp_path / "custom.toml").write_text(
        'name = "custom_app"\nartifact = "missing.apk"\npackage = "com.custom"\n'
    )
    with patch("android_bench.cli.setup_images") as setup_images:
        result = CliRunner().invoke(app, ["setup", "--catalog", str(tmp_path)])
    assert result.exit_code == 0, result.output
    setup_images.assert_called_once_with(load_catalog(tmp_path).definitions)


def test_web_command_starts_server(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    with patch("android_bench.web.server.run_server") as run_server_mock:
        web_command(results_dir, host="0.0.0.0", port=9090)

    run_server_mock.assert_called_once_with(
        results_dir=results_dir.resolve(),
        host="0.0.0.0",
        port=9090,
    )





