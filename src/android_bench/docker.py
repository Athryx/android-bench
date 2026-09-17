from __future__ import annotations

from kexploit_utils import build_docker

from android_bench.catalog import CHALLENGES, DockerTag, repository_root


def validate_artifacts() -> None:
    missing = [str(item.artifact_path) for item in CHALLENGES if not item.artifact_path.is_file()]
    if missing:
        formatted = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(f"Missing challenge artifacts:\n{formatted}")


def setup_images() -> None:
    root = repository_root()
    validate_artifacts()
    build_docker(root, DockerTag.BASE, dockerfile=root / "docker" / "base.Dockerfile")
    for challenge in CHALLENGES:
        build_docker(root, challenge.docker_tag, dockerfile=challenge.dockerfile_path)
