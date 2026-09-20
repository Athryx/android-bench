from pathlib import Path
from unittest.mock import MagicMock, patch

from kbench import GlobalRunState, Score
from kexploit_agent import Model, ModelConfig

from android_bench.runner import run_challenge


class _Score(Score):
    @property
    def score(self) -> float:
        return 1.0


def test_run_challenge_passes_internet_setting_to_sandbox(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    state.run_group = MagicMock()
    challenge = MagicMock()
    challenge.name = "internet-test"
    challenge.tag = "android-bench:test"
    challenge.cuttlefish_template = "challenge6"
    challenge.internet_enabled = True
    challenge.model_config = ModelConfig(model=Model.GPT_6_ASTRA)
    challenge.system_prompt.return_value = "test prompt"
    challenge.run.return_value = _Score()

    container = MagicMock()
    sandbox = MagicMock()
    sandbox.__enter__.return_value = sandbox
    sandbox.sandbox = container
    sandbox.container_adb_host = "cuttlefish:6000"

    with patch("android_bench.runner.AndroidBenchSandbox", return_value=sandbox) as cls:
        result = run_challenge(state, challenge)

    assert result.score.score == 1.0
    cls.assert_called_once_with(
        state,
        "android-bench:test",
        "challenge6",
        cls.call_args.args[3],
        name="internet-test",
        internet_enabled=True,
        extra_hosts={"api.openai.com": "127.0.0.1"},
    )


def test_run_challenge_copies_agent_history(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    state.run_group = MagicMock()
    challenge = MagicMock()
    challenge.name = "transcript-test"
    challenge.tag = "android-bench:test"
    challenge.cuttlefish_template = "challenge6"
    challenge.internet_enabled = False
    challenge.model_config = ModelConfig(model=Model.GPT_6_ASTRA)
    challenge.system_prompt.return_value = "test prompt"
    challenge.run.return_value = _Score()

    history_file = tmp_path / "raw_history.jsons"
    history_file.write_text('{"event": "init"}\n')

    agent = MagicMock()
    agent.history_path = history_file
    challenge.harness.create_agent.return_value = agent

    sandbox = MagicMock()
    sandbox.__enter__.return_value = sandbox
    sandbox.sandbox = MagicMock()
    sandbox.container_adb_host = "cuttlefish:6000"

    with patch("android_bench.runner.AndroidBenchSandbox", return_value=sandbox):
        result = run_challenge(state, challenge)

    assert result.score.score == 1.0
    solution_dir = tmp_path / "transcript-test"
    assert (solution_dir / "results.json").is_file()
    assert (solution_dir / "agent_transcript.jsons").is_file()
    assert (solution_dir / "agent_transcript.jsons").read_text() == '{"event": "init"}\n'


def test_run_challenge_summarizes_agent_history_before_copy(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    state.run_group = MagicMock()
    challenge = MagicMock()
    challenge.name = "summary-test"
    challenge.tag = "android-bench:test"
    challenge.cuttlefish_template = "challenge6"
    challenge.internet_enabled = False
    challenge.summarize = True
    challenge.model_config = ModelConfig(model=Model.GPT_6_ASTRA)
    challenge.system_prompt.return_value = "test prompt"
    challenge.run.return_value = _Score()

    history_file = tmp_path / "raw_history_summary.jsons"
    history_file.write_text('{"event": "init"}\n')

    agent = MagicMock()
    agent.history_path = history_file
    challenge.harness.create_agent.return_value = agent

    sandbox = MagicMock()
    sandbox.__enter__.return_value = sandbox
    sandbox.sandbox = MagicMock()
    sandbox.container_adb_host = "cuttlefish:6000"

    def summarize(path: Path) -> None:
        path.write_text(path.read_text() + '{"event": "summary"}\n')

    with (
        patch("android_bench.runner.AndroidBenchSandbox", return_value=sandbox),
        patch("android_bench.runner.summarize_log", side_effect=summarize) as summarize_log,
    ):
        run_challenge(state, challenge)

    expected = '{"event": "init"}\n{"event": "summary"}\n'
    summarize_log.assert_called_once_with(history_file)
    assert history_file.read_text() == expected
    assert (tmp_path / "summary-test" / "agent_transcript.jsons").read_text() == expected


def test_run_challenge_copies_agent_history_on_failure(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    state.run_group = MagicMock()
    challenge = MagicMock()
    challenge.name = "transcript-failure-test"
    challenge.tag = "android-bench:test"
    challenge.cuttlefish_template = "challenge6"
    challenge.internet_enabled = False
    challenge.model_config = ModelConfig(model=Model.GPT_6_ASTRA)
    challenge.system_prompt.return_value = "test prompt"
    challenge.run.side_effect = RuntimeError("challenge run failed")

    history_file = tmp_path / "raw_history_failure.jsons"
    history_file.write_text('{"event": "crashed"}\n')

    agent = MagicMock()
    agent.history_path = history_file
    challenge.harness.create_agent.return_value = agent

    sandbox = MagicMock()
    sandbox.__enter__.return_value = sandbox
    sandbox.sandbox = MagicMock()
    sandbox.container_adb_host = "cuttlefish:6000"

    import pytest

    with patch("android_bench.runner.AndroidBenchSandbox", return_value=sandbox):
        with pytest.raises(RuntimeError, match="challenge run failed"):
            run_challenge(state, challenge)

    solution_dir = tmp_path / "transcript-failure-test"
    assert (solution_dir / "agent_transcript.jsons").is_file()
    assert (solution_dir / "agent_transcript.jsons").read_text() == '{"event": "crashed"}\n'


def test_run_challenge_calls_prepare_solution(tmp_path: Path) -> None:
    state = MagicMock(spec=GlobalRunState)
    state.solutions_folder = tmp_path
    state.run_group = MagicMock()
    challenge = MagicMock()
    challenge.name = "prepare-test"
    challenge.tag = "android-bench:test"
    challenge.cuttlefish_template = "challenge6"
    challenge.internet_enabled = False
    challenge.model_config = ModelConfig(model=Model.GPT_6_ASTRA)
    challenge.system_prompt.return_value = "test prompt"
    challenge.run.return_value = _Score()

    sandbox = MagicMock()
    sandbox.__enter__.return_value = sandbox
    sandbox.sandbox = MagicMock()
    sandbox.container_adb_host = "cuttlefish:6000"

    with patch("android_bench.runner.AndroidBenchSandbox", return_value=sandbox):
        run_challenge(state, challenge)

    challenge.prepare_solution.assert_called_once_with(tmp_path / "prepare-test")
