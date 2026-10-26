from pathlib import Path

import pytest
from pydantic import ValidationError

from android_bench.catalog import load_catalog, repository_root
from android_bench.config import BenchmarkConfig

CHALLENGES = load_catalog().defaults
ALL_CHALLENGES = load_catalog().definitions
TEST_CHALLENGES = tuple(item for item in ALL_CHALLENGES if not item.default_enabled)


def test_repository_catalog_loads_without_requiring_private_artifacts() -> None:
    assert len(CHALLENGES) == 12
    assert len({item.name for item in CHALLENGES}) == 12
    assert len({item.package for item in CHALLENGES}) == 12
    assert all(isinstance(item.artifact, Path) for item in CHALLENGES)
    assert all(item.artifact.is_absolute() for item in CHALLENGES)
    assert all(item.default_enabled for item in CHALLENGES)
    assert all(item.apps_to_install == () for item in CHALLENGES)


def test_select_defaults_to_every_challenge_and_preserves_selection_order() -> None:
    assert load_catalog().select(None) == CHALLENGES
    selected = load_catalog().select(["vlc", "firefox"])
    assert [item.name for item in selected] == ["vlc", "firefox"]


def test_custom_catalog_resolves_paths_and_excludes_disabled_defaults(tmp_path: Path) -> None:
    (tmp_path / "a.toml").write_text(
        'name = "custom"\nartifact = "apps/missing.apk"\npackage = "com.custom"\n'
        'install_app = true\ncuttlefish_template = "custom-template"\n'
        'load_template_apps = false\nenabled_capabilities = ["file_write"]\n'
    )
    (tmp_path / "b.toml").write_text(
        'name = "optional"\nartifact = "other.apk"\npackage = "com.optional"\n'
        'default_enabled = false\ndocker_tag = "custom:tag"\n'
    )

    catalog = load_catalog(tmp_path)
    assert [item.name for item in catalog.defaults] == ["custom"]
    custom = catalog.by_name["custom"]
    assert custom.artifact == tmp_path / "apps/missing.apk"
    assert not custom.artifact.exists()
    assert custom.apps_to_install == ("/challenge/missing.apk",)
    assert custom.cuttlefish_template == "custom-template"
    assert not custom.load_template_apps
    assert catalog.by_name["optional"].docker_tag == "custom:tag"
    assert [item.name for item in catalog.select(["optional", "custom"])] == [
        "optional", "custom",
    ]


@pytest.mark.parametrize("names", [[], ["vlc", "vlc"], ["unknown"]])
def test_catalog_rejects_invalid_selections(names: list[str]) -> None:
    with pytest.raises(ValueError):
        load_catalog().select(names)


def test_catalog_rejects_duplicate_names(tmp_path: Path) -> None:
    definition = 'name = "duplicate"\nartifact = "missing.apk"\npackage = "com.example"\n'
    (tmp_path / "a.toml").write_text(definition)
    (tmp_path / "b.toml").write_text(definition)
    with pytest.raises(ValueError, match="Duplicate challenge name"):
        load_catalog(tmp_path)


def test_config_accepts_custom_names_until_catalog_resolution() -> None:
    config = BenchmarkConfig.model_validate(
        {
            "name": "custom-run",
            "challenges": ["not_in_repository_catalog"],
            "harness": "codex",
            "model_config": {"model": "gpt-6-astra"},
        }
    )
    assert config.challenge_configs[0].name == "not_in_repository_catalog"
    with pytest.raises(ValueError, match="Unknown challenge names"):
        load_catalog().select([item.name for item in config.challenge_configs])


def test_omitted_challenges_have_no_config_overrides() -> None:
    config = BenchmarkConfig.model_validate(
        {"name": "defaults", "harness": "codex", "model_config": {"model": "gpt-6-astra"}}
    )
    assert config.challenge_configs == []


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
    [[], ["vlc", "vlc"]],
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
    from android_bench.models import Capability

    assert len(TEST_CHALLENGES) == 6
    for challenge in TEST_CHALLENGES:
        assert challenge.artifact == repository_root() / "challenges/apps/test_app.apk"
        assert challenge.package == "com.purdue.androidbench.testapp"
        assert challenge.apps_to_install == ("/challenge/test_app.apk",)
        assert not challenge.default_enabled
        assert challenge.vulnerability_details is not None
        assert "8888" in challenge.vulnerability_details
        assert "EXEC" in challenge.vulnerability_details
        assert "WRITE" in challenge.vulnerability_details
        assert "READ" in challenge.vulnerability_details
        assert "INTENT" in challenge.vulnerability_details
        assert "LEAK" in challenge.vulnerability_details

    # Test single-grader challenges
    cap_map = {
        "test_code_execution": Capability.CODE_EXECUTION,
        "test_file_write": Capability.FILE_WRITE,
        "test_file_read": Capability.FILE_READ,
        "test_intent": Capability.INTENT,
        "test_aslr_leak": Capability.ASLR_LEAK,
    }
    test_by_name = {ch.name: ch for ch in TEST_CHALLENGES}
    for name, expected_cap in cap_map.items():
        ch = test_by_name[name]
        assert ch.enabled_capabilities == (expected_cap,)

    # Test test_all challenge
    test_all = test_by_name["test_all"]
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
    assert config.challenges == ["test_code_execution", "test_all"]
    selected = load_catalog().select([item.name for item in config.challenge_configs])
    assert [ch.name for ch in selected] == [
        "test_code_execution",
        "test_all",
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
    assert c0.name == "element"
    assert c0.capabilities == [Capability.CODE_EXECUTION, Capability.FILE_WRITE]
    assert c0.solutions_folder == (tmp_path / "seeds/element").resolve()
    assert c0.extra_prompt == "Custom instructions for element"

    c1 = config.challenges[1]
    assert isinstance(c1, ChallengeConfig)
    assert c1.name == "vlc"
    assert c1.capabilities is None
    assert c1.solutions_folder is None
    assert c1.extra_prompt is None

    # Test challenge_configs property
    configs = config.challenge_configs
    assert len(configs) == 2
    assert configs[0].name == "element"
    assert configs[1].name == "vlc"


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
    assert config.challenges[0] == "vlc"
    assert isinstance(config.challenges[1], ChallengeConfig)
    assert config.challenges[1].name == "shareit"
    assert config.challenges[1].solutions_folder == Path("/tmp/shareit_seed")
    assert config.challenges[1].capabilities == [Capability.CODE_EXECUTION]
    assert config.challenges[1].extra_prompt == "Extra instructions"

    # challenge_configs normalizes strings to ChallengeConfig
    cfgs = config.challenge_configs
    assert len(cfgs) == 2
    assert cfgs[0].name == "vlc"
    assert cfgs[0].capabilities is None
    assert cfgs[1].name == "shareit"
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


def test_catalog_selection_uses_normalized_challenge_config_names() -> None:
    from android_bench.config import ChallengeConfig

    items = [
        ChallengeConfig(name="vlc"),
        ChallengeConfig(name="element"),
    ]
    selected = load_catalog().select([item.name for item in items])
    assert len(selected) == 2
    assert selected[0].name == "vlc"
    assert selected[1].name == "element"

