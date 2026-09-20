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
