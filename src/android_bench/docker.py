import json
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from kexploit_agent.sandbox import build_kagent_sandbox
from kexploit_utils import build_docker

from android_bench.catalog import (
    ChallengeDefinition,
    DockerTag,
    repository_root,
)


def ensure_test_app_built() -> Path:
    root = repository_root()
    apk_path = root / "challenges" / "apps" / "test_app.apk"
    if apk_path.is_file():
        return apk_path
    apk_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{root}:/workspace",
            "-w",
            "/workspace",
            DockerTag.BASE.value,
            "bash",
            "docker/test-app/build.sh",
            "challenges/apps/test_app.apk",
        ],
        check=True,
    )
    return apk_path


def grader_apk_path() -> Path:
    return repository_root() / "build" / "grader" / "grader.apk"


def ensure_grader_app_built() -> Path:
    root = repository_root()
    apk_path = grader_apk_path()
    apk_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-v",
            f"{root}:/workspace",
            "-w",
            "/workspace",
            DockerTag.BASE.value,
            "bash",
            "docker/grader-app/build.sh",
            "build/grader/grader.apk",
        ],
        check=True,
    )
    return apk_path


def validate_artifacts(
    challenges: tuple[ChallengeDefinition, ...],
) -> None:
    missing = [
        str(item.artifact_path)
        for item in challenges
        if not item.artifact_path.is_file()
    ]
    if missing:
        formatted = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(f"Missing challenge artifacts:\n{formatted}")


def build_challenge_image(challenge: ChallengeDefinition) -> None:
    """Build from an isolated context containing only this challenge's artifact."""
    with TemporaryDirectory(prefix="android-bench-image-") as temporary_directory:
        context = Path(temporary_directory)
        artifact_directory = context / "artifact"
        artifact_directory.mkdir()
        shutil.copy2(
            challenge.artifact_path, artifact_directory / challenge.artifact_path.name
        )
        dockerfile = context / "Dockerfile"
        dockerfile.write_text(
            f"FROM {DockerTag.BASE.value}\n"
            f"COPY {json.dumps(['artifact/', '/challenge/'])}\n",
            encoding="utf-8",
        )
        build_docker(context, challenge.docker_tag, dockerfile=dockerfile)


def setup_images(challenges: tuple[ChallengeDefinition, ...]) -> None:
    root = repository_root()
    test_app = (root / "challenges" / "apps" / "test_app.apk").resolve()
    needs_test_app = not test_app.is_file() and any(
        challenge.artifact_path.resolve() == test_app for challenge in challenges
    )
    validate_artifacts(
        tuple(
            challenge
            for challenge in challenges
            if not (needs_test_app and challenge.artifact_path.resolve() == test_app)
        )
    )

    build_kagent_sandbox()
    build_docker(root, DockerTag.BASE, dockerfile=root / "docker" / "base.Dockerfile")
    if needs_test_app:
        ensure_test_app_built()
    validate_artifacts(challenges)
    ensure_grader_app_built()
    for challenge in challenges:
        build_challenge_image(challenge)
