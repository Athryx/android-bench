from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from android_bench.models import Capability


class DockerTag(StrEnum):
    BASE = "android-bench-base:latest"


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


DEFAULT_CATALOG_PATH = repository_root() / "challenges"


class ChallengeDefinition(BaseModel):
    """A catalog entry, also persisted with its resolved artifact in run snapshots."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
    artifact: Path
    package: str = Field(min_length=1)
    docker_tag: str = Field(
        default_factory=lambda data: f"android-bench-{data['name'].replace('_', '-').lower()}:latest",
        min_length=1,
    )
    enabled_capabilities: tuple[Capability, ...] | None = None
    vulnerability_details: str | None = None
    install_app: bool = False
    cuttlefish_template: str = Field(default="challenge6", min_length=1)
    load_template_apps: bool = True
    default_enabled: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, name: str) -> str:
        if name == "catalog":
            raise ValueError("Challenge name 'catalog' is reserved for run catalog snapshots")
        return name

    @field_validator("enabled_capabilities")
    @classmethod
    def validate_capabilities(
        cls, capabilities: tuple[Capability, ...] | None
    ) -> tuple[Capability, ...] | None:
        if capabilities is not None:
            if not capabilities:
                raise ValueError("enabled_capabilities must not be empty")
            if len(set(capabilities)) != len(capabilities):
                raise ValueError("enabled_capabilities contains duplicates")
        return capabilities

    @property
    def artifact_path(self) -> Path:
        return self.artifact

    @property
    def apps_to_install(self) -> tuple[str, ...]:
        if not self.install_app:
            return ()
        return (f"/challenge/{self.artifact.name}",)


@dataclass(frozen=True, slots=True)
class Catalog:
    definitions: tuple[ChallengeDefinition, ...]
    by_name: Mapping[str, ChallengeDefinition] = field(init=False)

    def __post_init__(self) -> None:
        by_name: dict[str, ChallengeDefinition] = {}
        docker_tags: dict[str, str] = {}
        for definition in self.definitions:
            if definition.name in by_name:
                raise ValueError(f"Duplicate challenge name: {definition.name}")
            if definition.docker_tag in docker_tags:
                raise ValueError(
                    f"Duplicate Docker tag {definition.docker_tag!r} for challenges "
                    f"{docker_tags[definition.docker_tag]!r} and {definition.name!r}"
                )
            by_name[definition.name] = definition
            docker_tags[definition.docker_tag] = definition.name
        object.__setattr__(self, "by_name", MappingProxyType(by_name))

    @property
    def defaults(self) -> tuple[ChallengeDefinition, ...]:
        return tuple(item for item in self.definitions if item.default_enabled)

    def select(self, names: Sequence[str] | None) -> tuple[ChallengeDefinition, ...]:
        if names is None:
            if not self.defaults:
                raise ValueError("Challenge catalog has no default-enabled challenges")
            return self.defaults
        if not names:
            raise ValueError("Challenge selection must not be empty")
        if len(set(names)) != len(names):
            raise ValueError("Challenge selection contains duplicate names")
        unknown = [name for name in names if name not in self.by_name]
        if unknown:
            raise ValueError(f"Unknown challenge names: {', '.join(unknown)}")
        return tuple(self.by_name[name] for name in names)


def load_catalog(path: Path | None = None) -> Catalog:
    """Load TOML definitions, resolving artifact paths against the catalog directory."""
    directory = (path if path is not None else DEFAULT_CATALOG_PATH).expanduser().resolve()
    if not directory.is_dir():
        raise FileNotFoundError(f"Challenge catalog directory does not exist: {directory}")
    files = sorted(directory.glob("*.toml"))
    if not files:
        raise ValueError(f"Challenge catalog contains no TOML definitions: {directory}")

    definitions: list[ChallengeDefinition] = []
    for file in files:
        try:
            with file.open("rb") as stream:
                definition = ChallengeDefinition.model_validate(tomllib.load(stream))
        except (tomllib.TOMLDecodeError, ValidationError) as error:
            raise ValueError(f"Invalid challenge definition in {file}: {error}") from error
        artifact = (directory / definition.artifact).resolve()
        definitions.append(definition.model_copy(update={"artifact": artifact}))
    return Catalog(tuple(definitions))
