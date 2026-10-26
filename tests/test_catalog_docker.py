import json
from pathlib import Path
from unittest.mock import patch

import pytest

from android_bench.catalog import ChallengeDefinition, DockerTag
from android_bench.docker import build_challenge_image, setup_images


def challenge_for(artifact: Path, name: str = "custom") -> ChallengeDefinition:
    return ChallengeDefinition(
        name=name,
        docker_tag=f"android-bench-{name}:latest",
        artifact=artifact,
        package="com.example.app",
    )


@pytest.mark.parametrize("basename", ["custom.apk", 'a [1] + \"quoted\" app.apkm', "app.xapk"])
def test_challenge_image_isolated_context(tmp_path: Path, basename: str) -> None:
    artifact = tmp_path / basename
    artifact.write_bytes(b"selected artifact")
    (tmp_path / "private.apk").write_bytes(b"not selected")
    challenge = challenge_for(artifact)
    contexts: list[Path] = []

    def inspect_build(context: Path, tag: str, *, dockerfile: Path) -> None:
        contexts.append(context)
        assert context != tmp_path
        assert tag == challenge.docker_tag
        assert set(context.iterdir()) == {dockerfile, context / "artifact"}
        assert list((context / "artifact").iterdir()) == [context / "artifact" / basename]
        assert (context / "artifact" / basename).read_bytes() == b"selected artifact"
        lines = dockerfile.read_text().splitlines()
        assert lines[0] == f"FROM {DockerTag.BASE.value}"
        assert json.loads(lines[1].removeprefix("COPY ")) == ["artifact/", "/challenge/"]

    with patch("android_bench.docker.build_docker", side_effect=inspect_build):
        build_challenge_image(challenge)

    assert len(contexts) == 1
    assert not contexts[0].exists()
    assert artifact.read_bytes() == b"selected artifact"


def test_setup_only_builds_selected_artifacts(tmp_path: Path) -> None:
    artifact = tmp_path / "synthetic.apk"
    artifact.touch()
    selected = challenge_for(artifact, "synthetic")
    with (
        patch("android_bench.docker.repository_root", return_value=tmp_path),
        patch("android_bench.docker.build_kagent_sandbox") as sandbox,
        patch("android_bench.docker.build_docker") as base,
        patch("android_bench.docker.ensure_grader_app_built") as grader,
        patch("android_bench.docker.ensure_test_app_built") as test_app,
        patch("android_bench.docker.build_challenge_image") as image,
    ):
        setup_images((selected,))

    sandbox.assert_called_once_with()
    base.assert_called_once_with(
        tmp_path, DockerTag.BASE, dockerfile=tmp_path / "docker" / "base.Dockerfile"
    )
    grader.assert_called_once_with()
    test_app.assert_not_called()
    image.assert_called_once_with(selected)


@pytest.mark.parametrize("existing", [False, True])
def test_setup_builds_selected_test_app_only_when_missing(tmp_path: Path, existing: bool) -> None:
    artifact = tmp_path / "challenges" / "apps" / "test_app.apk"
    artifact.parent.mkdir(parents=True)
    if existing:
        artifact.touch()
    selected = challenge_for(artifact, "synthetic")

    def build_test_app() -> Path:
        artifact.touch()
        return artifact

    with (
        patch("android_bench.docker.repository_root", return_value=tmp_path),
        patch("android_bench.docker.build_kagent_sandbox"),
        patch("android_bench.docker.build_docker"),
        patch("android_bench.docker.ensure_grader_app_built"),
        patch("android_bench.docker.ensure_test_app_built", side_effect=build_test_app) as test_app,
        patch("android_bench.docker.build_challenge_image") as image,
    ):
        setup_images((selected,))

    assert test_app.call_count == (0 if existing else 1)
    image.assert_called_once_with(selected)


def test_setup_missing_selected_artifact_fails_before_docker(tmp_path: Path) -> None:
    selected = challenge_for(tmp_path / "test_app.apk")
    with (
        patch("android_bench.docker.repository_root", return_value=tmp_path),
        patch("android_bench.docker.build_kagent_sandbox") as sandbox,
        patch("android_bench.docker.ensure_test_app_built") as test_app,
    ):
        with pytest.raises(FileNotFoundError, match="Missing challenge artifacts"):
            setup_images((selected,))

    sandbox.assert_not_called()
    test_app.assert_not_called()


def test_challenge_context_removed_after_failed_build(tmp_path: Path) -> None:
    artifact = tmp_path / "custom.apk"
    artifact.touch()
    contexts: list[Path] = []

    def fail_build(context: Path, tag: str, *, dockerfile: Path) -> None:
        contexts.append(context)
        raise RuntimeError("image build failed")

    with patch("android_bench.docker.build_docker", side_effect=fail_build):
        with pytest.raises(RuntimeError, match="image build failed"):
            build_challenge_image(challenge_for(artifact))

    assert not contexts[0].exists()
