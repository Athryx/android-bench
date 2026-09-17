from pathlib import Path

import pytest
from pydantic import ValidationError

from android_bench.catalog import (
    CHALLENGES,
    ChallengeName,
    repository_root,
    select_challenges,
)
from android_bench.config import BenchmarkConfig
from android_bench.docker import validate_artifacts


def test_all_twelve_artifacts_and_dockerfiles_exist() -> None:
    assert len(CHALLENGES) == 12
    assert len({item.name for item in CHALLENGES}) == 12
    assert len({item.package for item in CHALLENGES}) == 12
    validate_artifacts()
    assert all(item.dockerfile_path.is_file() for item in CHALLENGES)


def test_select_defaults_to_every_challenge_and_preserves_selection_order() -> None:
    assert select_challenges(None) == CHALLENGES
    selected = select_challenges([ChallengeName.VLC, ChallengeName.FIREFOX])
    assert [item.name for item in selected] == [ChallengeName.VLC, ChallengeName.FIREFOX]


def test_config_parses_runtime_model(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        """{
          "name": "smoke",
          "num_instances": 2,
          "challenges": ["firefox", "vlc"],
          "harness": "pi",
          "internet_enabled": true,
          "model_config": {"model": "deepseek-v4.1-flash"},
          "max_reprompts": 3
        }"""
    )
    config = BenchmarkConfig.from_file(path)
    assert config.name == "smoke"
    assert config.internet_enabled
    assert config.agent_model_config.model.value == "deepseek/deepseek-v4.1-flash"
    assert config.max_reprompts == 3


def test_example_config_uses_extended_model_fields() -> None:
    config = BenchmarkConfig.from_file(
        repository_root() / "benchmark_config.example.json"
    )

    assert config.agent_model_config.model.value == "gpt-6-astra"
    assert config.internet_enabled
    assert config.agent_model_config.model_effort is not None
    assert config.agent_model_config.model_effort.value == "xhigh"
    assert config.agent_model_config.temperature == 0.2
    assert config.agent_model_config.max_tokens == 65536
    assert config.agent_model_config.top_p == 0.95
    assert config.agent_model_config.timeout_seconds == 3600
    assert config.agent_model_config.thinking_budget == 32768


@pytest.mark.parametrize(
    "challenges",
    [[], ["vlc", "vlc"], ["not_a_challenge"]],
)
def test_config_rejects_invalid_challenge_lists(challenges: list[str]) -> None:
    with pytest.raises(ValidationError):
        BenchmarkConfig.model_validate(
            {
                "name": "bad",
                "challenges": challenges,
                "harness": "codex",
                "model_config": {"model": "gpt-6-astra"},
            }
        )
