import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import patch
from zipfile import ZipFile

import pytest

from android_bench.catalog import repository_root


def load_installer() -> ModuleType:
    path = repository_root() / "docker" / "install_apps.py"
    spec = importlib.util.spec_from_file_location("android_bench_install_apps", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bundle_selects_one_abi_and_one_language(tmp_path: Path) -> None:
    installer = load_installer()
    archive_path = tmp_path / "bundle.apkm"
    with ZipFile(archive_path, "w") as archive:
        for name in (
            "base.apk",
            "split_config.arm64_v8a.apk",
            "split_config.armeabi_v7a.apk",
            "split_Admob.config.en.apk",
            "split_Admob.config.de.apk",
        ):
            archive.writestr(name, b"fixture APK")

    with ZipFile(archive_path) as archive:
        selected = installer.selected_apk_names(archive.namelist(), "arm64_v8a")

    assert selected == [
        "base.apk",
        "split_Admob.config.en.apk",
        "split_config.arm64_v8a.apk",
    ]


def test_bundle_selector_keeps_density_and_feature_splits() -> None:
    installer = load_installer()
    names = [
        "base.apk",
        "config.mdpi.apk",
        "split_feature.apk",
        "split_feature.config.en.apk",
        "split_feature.config.fr.apk",
    ]
    assert installer.selected_apk_names(names, "arm64_v8a") == [
        "base.apk",
        "config.mdpi.apk",
        "split_feature.apk",
        "split_feature.config.en.apk",
    ]


def test_installation_candidates_adds_missing_challenge_artifact(
    tmp_path: Path,
) -> None:
    installer = load_installer()
    app_dir = tmp_path / "apps"
    challenge_dir = tmp_path / "challenge"
    app_dir.mkdir()
    challenge_dir.mkdir()
    bulk_app = app_dir / "bulk.apk"
    bulk_app.write_bytes(b"bulk")
    (app_dir / "grader.apk").write_bytes(b"grader")
    challenge_copy = challenge_dir / "bulk.apk"
    challenge_copy.write_bytes(b"analysis")
    challenge_target = challenge_dir / "test_app.apk"
    challenge_target.write_bytes(b"target")

    assert installer.installation_candidates(app_dir, challenge_dir) == [
        bulk_app,
        challenge_target,
    ]


@pytest.mark.parametrize("suffix", [".apk", ".apkm", ".xapk"])
def test_explicit_install_only_uses_requested_artifact(tmp_path: Path, suffix: str) -> None:
    installer = load_installer()
    artifact = tmp_path / f"target{suffix}"
    artifact.touch()
    with (
        patch.object(installer.sys, "argv", ["installer", "device", str(artifact)]),
        patch.object(installer, "APP_DIR", tmp_path),
        patch.object(installer, "installation_candidates") as discover,
        patch.object(installer, "run_adb", return_value="arm64-v8a,armeabi-v7a\n") as adb,
        patch.object(installer, "install_archive") as archive,
    ):
        installer.main()

    discover.assert_not_called()
    if suffix == ".apk":
        adb.assert_any_call("device", "install", "-t", "-r", str(artifact))
        archive.assert_not_called()
    else:
        archive.assert_called_once_with("device", artifact, "arm64_v8a")
    assert artifact.exists()


def test_installer_without_paths_preserves_discovery(tmp_path: Path) -> None:
    installer = load_installer()
    artifact = tmp_path / "app.apk"
    artifact.touch()
    with (
        patch.object(installer.sys, "argv", ["installer", "device"]),
        patch.object(installer, "installation_candidates", return_value=[artifact]) as discover,
        patch.object(installer, "run_adb", return_value="arm64-v8a\n") as adb,
    ):
        installer.main()

    discover.assert_called_once_with()
    adb.assert_any_call("device", "install", "-t", "-r", str(artifact))


@pytest.mark.parametrize("basename", ["missing.apk", "unsupported.txt"])
def test_installer_rejects_invalid_explicit_artifact(tmp_path: Path, basename: str) -> None:
    installer = load_installer()
    artifact = tmp_path / basename
    if artifact.suffix == ".txt":
        artifact.touch()
    with (
        patch.object(installer.sys, "argv", ["installer", "device", str(artifact)]),
        patch.object(installer, "run_adb") as adb,
    ):
        with pytest.raises((FileNotFoundError, ValueError)):
            installer.main()

    adb.assert_not_called()
