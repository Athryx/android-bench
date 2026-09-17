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
