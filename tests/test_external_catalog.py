import tomllib
from pathlib import Path

import pytest
import tomli_w

from android_bench.catalog import ChallengeDefinition, load_catalog, repository_root
from android_bench.models import Capability


def write_definition(directory: Path, name: str, **fields: object) -> Path:
    path = directory / f"{name}.toml"
    data = {"name": name, "artifact": f"apps/{name}.apk", "package": f"com.example.{name}"}
    path.write_text(tomli_w.dumps(data | fields))
    return path


def test_external_catalog_resolves_artifacts_and_applies_defaults(tmp_path: Path) -> None:
    write_definition(tmp_path, "custom_app")

    catalog = load_catalog(tmp_path)
    definition = catalog.by_name["custom_app"]

    assert catalog.definitions == (definition,)
    assert catalog.defaults == (definition,)
    assert definition.artifact == (tmp_path / "apps/custom_app.apk").resolve()
    assert definition.artifact_path == definition.artifact
    assert definition.docker_tag == "android-bench-custom-app:latest"
    assert definition.enabled_capabilities is None
    assert definition.vulnerability_details is None
    assert not definition.install_app
    assert definition.apps_to_install == ()
    assert definition.cuttlefish_template == "challenge6"
    assert definition.load_template_apps


def test_explicit_selection_includes_disabled_entries_in_requested_order(tmp_path: Path) -> None:
    write_definition(tmp_path, "regular")
    write_definition(tmp_path, "synthetic", default_enabled=False, install_app=True)
    catalog = load_catalog(tmp_path)

    assert [definition.name for definition in catalog.select(None)] == ["regular"]
    assert [definition.name for definition in catalog.select(["synthetic", "regular"])] == [
        "synthetic", "regular"
    ]
    assert catalog.by_name["synthetic"].apps_to_install == ("/challenge/synthetic.apk",)


@pytest.mark.parametrize("names", [[], ["custom", "custom"], ["missing"]])
def test_selection_rejects_empty_duplicate_or_unknown_names(
    tmp_path: Path, names: list[str]
) -> None:
    write_definition(tmp_path, "custom")
    with pytest.raises(ValueError):
        load_catalog(tmp_path).select(names)


def test_duplicate_definition_names_are_rejected(tmp_path: Path) -> None:
    path = write_definition(tmp_path, "custom")
    (tmp_path / "duplicate.toml").write_text(path.read_text())
    with pytest.raises(ValueError, match="Duplicate challenge name: custom"):
        load_catalog(tmp_path)


def test_generated_docker_tag_is_lowercase(tmp_path: Path) -> None:
    write_definition(tmp_path, "Custom_APP")
    definition = load_catalog(tmp_path).by_name["Custom_APP"]
    assert definition.docker_tag == "android-bench-custom-app:latest"


@pytest.mark.parametrize("names", [("foo_bar", "foo-bar"), ("CUSTOM", "custom")])
def test_generated_docker_tag_collisions_are_rejected(
    tmp_path: Path, names: tuple[str, str]
) -> None:
    for name in names:
        write_definition(tmp_path, name)
    with pytest.raises(ValueError, match="Duplicate Docker tag") as error:
        load_catalog(tmp_path)
    assert all(name in str(error.value) for name in names)


def test_explicit_docker_tag_collisions_are_rejected(tmp_path: Path) -> None:
    write_definition(tmp_path, "first", docker_tag="same:latest")
    write_definition(tmp_path, "second", docker_tag="same:latest")
    with pytest.raises(ValueError, match="Duplicate Docker tag 'same:latest'"):
        load_catalog(tmp_path)


def test_snapshot_roundtrip_preserves_absolute_artifact(tmp_path: Path) -> None:
    write_definition(
        tmp_path,
        "custom",
        artifact="nested/apps/payload.apk",
        install_app=True,
        enabled_capabilities=["file_read"],
        vulnerability_details="Exact details: \\n and Unicode: λ\nsecond line",
        cuttlefish_template="custom-template",
        load_template_apps=False,
    )
    original = load_catalog(tmp_path).by_name["custom"]

    restored = ChallengeDefinition.model_validate_json(original.model_dump_json())
    toml_snapshot = tomli_w.dumps(original.model_dump(mode="json", exclude_none=True))
    restored_toml = ChallengeDefinition.model_validate(tomllib.loads(toml_snapshot))

    assert original == restored == restored_toml
    assert restored.artifact.is_absolute()
    assert restored.artifact_path == tmp_path / "nested/apps/payload.apk"
    assert restored.apps_to_install == ("/challenge/payload.apk",)
    assert restored.enabled_capabilities == (Capability.FILE_READ,)
    assert restored.cuttlefish_template == "custom-template"
    assert not restored.load_template_apps


def test_absolute_artifact_and_custom_docker_tag_are_preserved(tmp_path: Path) -> None:
    artifact = tmp_path / "elsewhere/target.apkm"
    write_definition(tmp_path, "custom", artifact=str(artifact), docker_tag="local:custom")
    definition = load_catalog(tmp_path).by_name["custom"]

    assert definition.artifact == artifact
    assert definition.docker_tag == "local:custom"


@pytest.mark.parametrize("capabilities", [[], ["file_read", "file_read"], ["invalid"]])
def test_invalid_capabilities_are_rejected(tmp_path: Path, capabilities: list[str]) -> None:
    write_definition(tmp_path, "custom", enabled_capabilities=capabilities)
    with pytest.raises(ValueError, match="custom.toml"):
        load_catalog(tmp_path)


@pytest.mark.parametrize(
    "fields",
    [{"name": "../unsafe"}, {"name": ""}, {"docker_tag": ""}, {"cuttlefish_template": ""}],
)
def test_invalid_identifiers_and_empty_settings_are_rejected(
    tmp_path: Path, fields: dict[str, str]
) -> None:
    path = tmp_path / "custom.toml"
    data = {"name": "custom", "artifact": "apps/app.apk", "package": "com.example.app"}
    path.write_text(tomli_w.dumps(data | fields))
    with pytest.raises(ValueError, match="custom.toml"):
        load_catalog(tmp_path)


def test_catalog_name_is_reserved_for_run_snapshots(tmp_path: Path) -> None:
    write_definition(tmp_path, "catalog")
    with pytest.raises(ValueError, match="reserved for run catalog snapshots"):
        load_catalog(tmp_path)


def test_catalog_without_defaults_requires_explicit_selection(tmp_path: Path) -> None:
    write_definition(tmp_path, "synthetic", default_enabled=False)
    catalog = load_catalog(tmp_path)
    assert catalog.defaults == ()
    with pytest.raises(ValueError, match="no default-enabled"):
        catalog.select(None)
    assert catalog.select(["synthetic"]) == catalog.definitions


def test_malformed_toml_error_includes_filename(tmp_path: Path) -> None:
    (tmp_path / "broken.toml").write_text('name = "unterminated')
    with pytest.raises(ValueError, match="broken.toml"):
        load_catalog(tmp_path)


def test_missing_and_empty_catalogs_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="catalog directory"):
        load_catalog(tmp_path / "missing")
    with pytest.raises(ValueError, match="no TOML definitions"):
        load_catalog(tmp_path)


def test_builtin_catalog_preserves_production_and_synthetic_definitions() -> None:
    catalog = load_catalog()
    assert len(catalog.definitions) == 18
    assert len(catalog.defaults) == 12
    assert all(not definition.install_app for definition in catalog.defaults)
    assert all(definition.enabled_capabilities == (
        Capability.CODE_EXECUTION, Capability.FILE_WRITE
    ) for definition in catalog.defaults)

    synthetic = tuple(item for item in catalog.definitions if not item.default_enabled)
    assert len(synthetic) == 6
    for definition in synthetic:
        assert definition.package == "com.purdue.androidbench.testapp"
        assert definition.artifact == repository_root() / "challenges/apps/test_app.apk"
        assert definition.install_app
        assert definition.apps_to_install == ("/challenge/test_app.apk",)
        assert definition.vulnerability_details is not None
        for command in ("EXEC", "WRITE", "READ", "INTENT", "LEAK", "8888"):
            assert command in definition.vulnerability_details
    assert set(catalog.by_name["test_all"].enabled_capabilities or ()) == set(Capability)
