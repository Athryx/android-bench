from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from android_bench.catalog import DockerTag
from android_bench.docker import (
    ensure_test_app_built,
    setup_images,
    validate_artifacts,
)


def test_validate_artifacts_missing(tmp_path: Path) -> None:
    fake_challenge = MagicMock()
    fake_challenge.artifact_path = tmp_path / "nonexistent.apk"

    with pytest.raises(FileNotFoundError, match="Missing challenge artifacts"):
        validate_artifacts((fake_challenge,))


def test_validate_artifacts_present(tmp_path: Path) -> None:
    fake_challenge = MagicMock()
    present_file = tmp_path / "app.apk"
    present_file.write_text("dummy")
    fake_challenge.artifact_path = present_file

    validate_artifacts((fake_challenge,))


def test_ensure_test_app_built_existing(tmp_path: Path) -> None:
    fake_root = tmp_path
    apk_dir = fake_root / "apps"
    apk_dir.mkdir(parents=True)
    apk = apk_dir / "test_app.apk"
    apk.write_text("exists")

    with patch("android_bench.docker.repository_root", return_value=fake_root), patch(
        "subprocess.run"
    ) as mock_run:
        result = ensure_test_app_built()
        assert result == apk
        mock_run.assert_not_called()


def test_ensure_test_app_built_generates(tmp_path: Path) -> None:
    fake_root = tmp_path

    with patch("android_bench.docker.repository_root", return_value=fake_root), patch(
        "subprocess.run"
    ) as mock_run:
        result = ensure_test_app_built()
        assert result == fake_root / "apps" / "test_app.apk"
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "docker" in args
        assert DockerTag.BASE.value in args


def test_setup_images_orchestration() -> None:
    with (
        patch("android_bench.docker.validate_artifacts") as mock_validate,
        patch("android_bench.docker.build_kagent_sandbox") as mock_build_sandbox,
        patch("android_bench.docker.build_docker") as mock_build_docker,
        patch("android_bench.docker.ensure_test_app_built") as mock_test_app,
    ):
        setup_images()

        mock_build_sandbox.assert_called_once()
        assert mock_validate.call_count == 2
        mock_test_app.assert_called_once()

        # BASE image must be built
        build_calls = [call[0][1] for call in mock_build_docker.call_args_list]
        assert DockerTag.BASE in build_calls
