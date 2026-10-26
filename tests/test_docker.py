from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from android_bench.catalog import DockerTag
from android_bench.docker import (
    ensure_grader_app_built,
    ensure_test_app_built,
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
    apk_dir = fake_root / "challenges" / "apps"
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
        assert result == fake_root / "challenges" / "apps" / "test_app.apk"
        assert mock_run.call_args.args[0][-1] == "challenges/apps/test_app.apk"
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "docker" in args
        assert DockerTag.BASE.value in args


def test_ensure_grader_app_built_outside_solver_image(tmp_path: Path) -> None:
    with patch("android_bench.docker.repository_root", return_value=tmp_path), patch(
        "subprocess.run"
    ) as mock_run:
        result = ensure_grader_app_built()

    assert result == tmp_path / "build" / "grader" / "grader.apk"
    assert result.parent.is_dir()
    command = mock_run.call_args.args[0]
    assert DockerTag.BASE.value in command
    assert "docker/grader-app/build.sh" in command
