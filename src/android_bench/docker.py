import os
import subprocess
from pathlib import Path

from kexploit_agent.sandbox import build_kagent_sandbox
from kexploit_utils import build_docker

from android_bench.catalog import (
    ALL_CHALLENGES,
    CHALLENGES,
    TEST_CHALLENGES,
    ChallengeDefinition,
    DockerTag,
    repository_root,
)


def ensure_test_app_built() -> Path:
    root = repository_root()
    apk_path = root / "apps" / "test_app.apk"
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
            "apps/test_app.apk",
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
    challenges: tuple[ChallengeDefinition, ...] = ALL_CHALLENGES,
) -> None:
    missing = [
        str(item.artifact_path)
        for item in challenges
        if not item.artifact_path.is_file()
    ]
    if missing:
        formatted = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(f"Missing challenge artifacts:\n{formatted}")


def setup_images() -> None:
    root = repository_root()
    validate_artifacts(CHALLENGES)
    build_kagent_sandbox()
    build_docker(root, DockerTag.BASE, dockerfile=root / "docker" / "base.Dockerfile")
    ensure_grader_app_built()
    ensure_test_app_built()
    validate_artifacts(TEST_CHALLENGES)
    for challenge in ALL_CHALLENGES:
        build_docker(root, challenge.docker_tag, dockerfile=challenge.dockerfile_path)
