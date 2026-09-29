import importlib.util
from pathlib import Path
from types import ModuleType

from android_bench.catalog import repository_root


def load_installer() -> ModuleType:
    path = repository_root() / "docker" / "install_apps.py"
    spec = importlib.util.spec_from_file_location("android_bench_install_apps", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shareit_bundle_selects_one_abi_and_one_language() -> None:
    installer = load_installer()
    archive_path = next(
        path
        for path in (repository_root() / "apps").glob("*.apkm")
        if path.name.startswith("com.lenovo.anyshare")
    )
    from zipfile import ZipFile

    with ZipFile(archive_path) as archive:
        selected = installer.selected_apk_names(archive.namelist(), "arm64_v8a")

    assert "base.apk" in selected
    assert "split_config.arm64_v8a.apk" in selected
    assert all("armeabi_v7a" not in name for name in selected)
    assert all(not name.endswith(".de.apk") for name in selected)
    assert "split_Admob.config.en.apk" in selected
    assert len(selected) < 30


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
