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
    assert all(item.apps_to_install == () for item in CHALLENGES)


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
          "summarize": true,
          "model_config": {"model": "deepseek-v4.1-flash"},
          "max_reprompts": 3
        }"""
    )
    config = BenchmarkConfig.from_file(path)
    assert config.name == "smoke"
    assert config.internet_enabled
    assert config.summarize
    assert config.agent_model_config.model.value == "deepseek/deepseek-v4.1-flash"
    assert config.max_reprompts == 3


def test_example_config_uses_extended_model_fields() -> None:
    config = BenchmarkConfig.from_file(
        repository_root() / "benchmark_config.example.toml"
    )

    assert config.agent_model_config.model.value == "gpt-6-astra"
    assert config.internet_enabled
    assert config.summarize
    assert config.agent_model_config.model_effort is not None
    assert config.agent_model_config.model_effort.value == "xhigh"
    assert config.agent_model_config.temperature == 0.2
    assert config.agent_model_config.max_tokens == 65536
    assert config.agent_model_config.top_p == 0.95
    assert config.agent_model_config.timeout_seconds == 3600
    assert config.agent_model_config.thinking_budget == 32768
    assert config.limits is not None
    assert config.limits.token_limit == 500000
    assert config.limits.turn_limit == 50
    assert config.limits.time_limit == 3600.0


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


def test_test_challenges_exist_and_configured_properly() -> None:
    from android_bench.catalog import (
        TEST_CHALLENGES,
        TEST_APP_ARTIFACT,
        TEST_APP_INSTALL_PATH,
        TEST_APP_PACKAGE,
    )
    from android_bench.models import Capability

    assert len(TEST_CHALLENGES) == 6
    for challenge in TEST_CHALLENGES:
        assert challenge.artifact == TEST_APP_ARTIFACT
        assert challenge.package == TEST_APP_PACKAGE
        assert challenge.apps_to_install == (TEST_APP_INSTALL_PATH,)
        assert challenge.artifact_path.is_file()
        assert challenge.dockerfile_path.is_file()
        assert challenge.vulnerability_details is not None
        assert "8888" in challenge.vulnerability_details
        assert "EXEC" in challenge.vulnerability_details
        assert "WRITE" in challenge.vulnerability_details
        assert "READ" in challenge.vulnerability_details
        assert "INTENT" in challenge.vulnerability_details
        assert "LEAK" in challenge.vulnerability_details

    # Test single-grader challenges
    cap_map = {
        ChallengeName.TEST_CODE_EXECUTION: Capability.CODE_EXECUTION,
        ChallengeName.TEST_FILE_WRITE: Capability.FILE_WRITE,
        ChallengeName.TEST_FILE_READ: Capability.FILE_READ,
        ChallengeName.TEST_INTENT: Capability.INTENT,
        ChallengeName.TEST_ASLR_LEAK: Capability.ASLR_LEAK,
    }
    test_by_name = {ch.name: ch for ch in TEST_CHALLENGES}
    for name, expected_cap in cap_map.items():
        ch = test_by_name[name]
        assert ch.enabled_capabilities == (expected_cap,)

    # Test test_all challenge
    test_all = test_by_name[ChallengeName.TEST_ALL]
    assert test_all.enabled_capabilities is not None
    assert set(test_all.enabled_capabilities) == set(Capability)


def test_config_accepts_test_challenges() -> None:
    config = BenchmarkConfig.model_validate(
        {
            "name": "test-run",
            "challenges": ["test_code_execution", "test_all"],
            "harness": "codex",
            "model_config": {"model": "gpt-6-astra"},
        }
    )
    assert config.challenges == [ChallengeName.TEST_CODE_EXECUTION, ChallengeName.TEST_ALL]
    selected = select_challenges(config.challenges)
    assert [ch.name for ch in selected] == [
        ChallengeName.TEST_CODE_EXECUTION,
        ChallengeName.TEST_ALL,
    ]


def test_config_parses_nested_limits() -> None:
    from decimal import Decimal

    config = BenchmarkConfig.model_validate(
        {
            "name": "limits-test",
            "harness": "codex",
            "model_config": {"model": "gpt-6-astra"},
            "limits": {
                "token_limit": 50000,
                "turn_limit": 25,
                "time_limit": 1800.0,
                "dollar_limit": "5.50",
            },
        }
    )
    assert config.limits is not None
    assert config.limits.token_limit == 50000
    assert config.limits.turn_limit == 25
    assert config.limits.time_limit == 1800.0
    assert config.limits.dollar_limit == Decimal("5.50")


def test_config_parses_flat_limits_and_timeout_alias() -> None:
    from decimal import Decimal

    config = BenchmarkConfig.model_validate(
        {
            "name": "flat-limits-test",
            "harness": "codex",
            "model_config": {"model": "gpt-6-astra"},
            "token_limit": 20000,
            "turn_limit": 10,
            "timeout_seconds": 600.0,
            "dollar_limit": 2.0,
        }
    )
    assert config.limits is not None
    assert config.limits.token_limit == 20000
    assert config.limits.turn_limit == 10
    assert config.limits.time_limit == 600.0
    assert config.limits.dollar_limit == Decimal("2.0")


def test_config_nested_limits_override_flat_timeout() -> None:
    config = BenchmarkConfig.model_validate(
        {
            "name": "override-test",
            "harness": "codex",
            "model_config": {"model": "gpt-6-astra"},
            "timeout_seconds": 300,
            "limits": {"time_limit": 900.0},
        }
    )
    assert config.limits is not None
    assert config.limits.time_limit == 900.0


def test_config_parses_challenge_config_table(tmp_path: Path) -> None:
    from android_bench.config import ChallengeConfig
    from android_bench.models import Capability

    toml_path = tmp_path / "challenge.toml"
    toml_path.write_text(
        """
        name = "custom-challenge-run"
        harness = "codex"
        
        [model_config]
        model = "gpt-6-astra"

        [[challenges]]
        name = "element"
        capabilities = ["code_execution", "file_write"]
        solutions_folder = "seeds/element"
        extra_prompt = "Custom instructions for element"

        [[challenges]]
        name = "vlc"
        """
    )
    config = BenchmarkConfig.from_file(toml_path)
    assert config.challenges is not None
    assert len(config.challenges) == 2

    c0 = config.challenges[0]
    assert isinstance(c0, ChallengeConfig)
    assert c0.name == ChallengeName.ELEMENT
    assert c0.capabilities == [Capability.CODE_EXECUTION, Capability.FILE_WRITE]
    assert c0.solutions_folder == (tmp_path / "seeds/element").resolve()
    assert c0.extra_prompt == "Custom instructions for element"

    c1 = config.challenges[1]
    assert isinstance(c1, ChallengeConfig)
    assert c1.name == ChallengeName.VLC
    assert c1.capabilities is None
    assert c1.solutions_folder is None
    assert c1.extra_prompt is None

    # Test challenge_configs property
    configs = config.challenge_configs
    assert len(configs) == 2
    assert configs[0].name == ChallengeName.ELEMENT
    assert configs[1].name == ChallengeName.VLC


def test_config_parses_mixed_challenges_and_aliases() -> None:
    from android_bench.config import ChallengeConfig
    from android_bench.models import Capability

    config = BenchmarkConfig.model_validate(
        {
            "name": "mixed-run",
            "harness": "codex",
            "model_config": {"model": "gpt-6-astra"},
            "challenges": [
                "vlc",
                {
                    "name": "shareit",
                    "solution_folder": "/tmp/shareit_seed",
                    "capabilities": ["code_execution"],
                    "extra_prompt": "Extra instructions",
                },
            ],
        }
    )
    assert config.challenges is not None
    assert config.challenges[0] == ChallengeName.VLC
    assert isinstance(config.challenges[1], ChallengeConfig)
    assert config.challenges[1].name == ChallengeName.SHAREIT
    assert config.challenges[1].solutions_folder == Path("/tmp/shareit_seed")
    assert config.challenges[1].capabilities == [Capability.CODE_EXECUTION]
    assert config.challenges[1].extra_prompt == "Extra instructions"

    # challenge_configs normalizes strings to ChallengeConfig
    cfgs = config.challenge_configs
    assert len(cfgs) == 2
    assert cfgs[0].name == ChallengeName.VLC
    assert cfgs[0].capabilities is None
    assert cfgs[1].name == ChallengeName.SHAREIT
    assert cfgs[1].capabilities == [Capability.CODE_EXECUTION]


def test_config_rejects_empty_and_duplicate_capabilities() -> None:
    with pytest.raises(ValidationError):
        BenchmarkConfig.model_validate(
            {
                "name": "bad-caps",
                "harness": "codex",
                "model_config": {"model": "gpt-6-astra"},
                "challenges": [
                    {"name": "element", "capabilities": []},
                ],
            }
        )

    with pytest.raises(ValidationError):
        BenchmarkConfig.model_validate(
            {
                "name": "dup-caps",
                "harness": "codex",
                "model_config": {"model": "gpt-6-astra"},
                "challenges": [
                    {"name": "element", "capabilities": ["code_execution", "code_execution"]},
                ],
            }
        )


def test_config_rejects_duplicate_challenges_with_mixed_types() -> None:
    with pytest.raises(ValidationError, match="challenges contains duplicate names"):
        BenchmarkConfig.model_validate(
            {
                "name": "dup-challenges",
                "harness": "codex",
                "model_config": {"model": "gpt-6-astra"},
                "challenges": [
                    "element",
                    {"name": "element", "extra_prompt": "more prompt"},
                ],
            }
        )


def test_select_challenges_handles_challenge_configs() -> None:
    from android_bench.config import ChallengeConfig

    items = [
        ChallengeName.VLC,
        ChallengeConfig(name=ChallengeName.ELEMENT),
    ]
    selected = select_challenges(items)
    assert len(selected) == 2
    assert selected[0].name == ChallengeName.VLC
    assert selected[1].name == ChallengeName.ELEMENT

