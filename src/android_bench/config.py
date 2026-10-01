from __future__ import annotations

import json
from pathlib import Path
import tomllib

from kexploit_agent import HarnessType, Limits, ModelConfig
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
import tomli_w

from android_bench.catalog import ChallengeName
from android_bench.models import Capability


class ChallengeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ChallengeName
    capabilities: list[Capability] | None = None
    solutions_folder: Path | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "solutions_folder",
            "solution_folder",
            "starting_solution",
            "starting_solutions_folder",
        ),
    )
    extra_prompt: str | None = None

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(
        cls, value: list[Capability] | None
    ) -> list[Capability] | None:
        if value is not None and not value:
            raise ValueError("capabilities must not be empty if specified")
        if value is not None and len(set(value)) != len(value):
            raise ValueError("capabilities contains duplicate values")
        return value


class BenchmarkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(min_length=1)
    num_instances: int | None = Field(default=None, ge=1)
    challenges: list[ChallengeName | ChallengeConfig] | None = None
    harness: HarnessType
    internet_enabled: bool = False
    summarize: bool = False
    agent_model_config: ModelConfig = Field(alias="model_config")
    max_reprompts: int = Field(default=2, ge=0)
    limits: Limits | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_limits(cls, data: object) -> object:
        if isinstance(data, dict):
            data = dict(data)
            flat_limits: dict[str, object] = {}
            for key in ("token_limit", "turn_limit", "time_limit", "dollar_limit"):
                if key in data:
                    flat_limits[key] = data.pop(key)
            if "timeout_seconds" in data and "time_limit" not in flat_limits:
                flat_limits["time_limit"] = data.pop("timeout_seconds")
            elif "timeout_seconds" in data:
                data.pop("timeout_seconds")

            if flat_limits:
                if "limits" in data and isinstance(data["limits"], dict):
                    merged = dict(flat_limits)
                    merged.update(data["limits"])
                    data["limits"] = merged
                elif "limits" not in data or data["limits"] is None:
                    data["limits"] = flat_limits
        return data

    @field_validator("challenges")
    @classmethod
    def reject_empty_or_duplicate_challenges(
        cls, value: list[ChallengeName | ChallengeConfig] | None
    ) -> list[ChallengeName | ChallengeConfig] | None:
        if value is not None and not value:
            raise ValueError("challenges must be omitted or contain at least one challenge")
        if value is not None:
            names = [
                item.name if isinstance(item, ChallengeConfig) else item
                for item in value
            ]
            if len(set(names)) != len(names):
                raise ValueError("challenges contains duplicate names")
        return value

    @property
    def challenge_configs(self) -> list[ChallengeConfig]:
        if self.challenges is None:
            from android_bench.catalog import CHALLENGES

            return [ChallengeConfig(name=d.name) for d in CHALLENGES]
        return [
            item if isinstance(item, ChallengeConfig) else ChallengeConfig(name=item)
            for item in self.challenges
        ]

    def resolve_paths(self, base_dir: Path) -> None:
        if self.challenges is not None:
            for item in self.challenges:
                if isinstance(item, ChallengeConfig) and item.solutions_folder is not None:
                    if not item.solutions_folder.is_absolute():
                        item.solutions_folder = (base_dir / item.solutions_folder).resolve()

    @classmethod
    def from_file(cls, path: Path) -> BenchmarkConfig:
        content = path.read_text(encoding="utf-8")
        if path.suffix == ".toml":
            config = cls.model_validate(tomllib.loads(content))
        elif path.suffix == ".json":
            config = cls.model_validate_json(content)
        else:
            try:
                config = cls.model_validate(tomllib.loads(content))
            except Exception:
                config = cls.model_validate_json(content)
        config.resolve_paths(path.parent.resolve())
        return config

    def formatted_toml(self) -> str:
        return tomli_w.dumps(self.model_dump(mode="json", by_alias=True, exclude_none=True))

    def formatted_json(self) -> str:
        return json.dumps(self.model_dump(mode="json", by_alias=True), indent=2) + "\n"
