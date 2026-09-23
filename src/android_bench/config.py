from __future__ import annotations

import json
from pathlib import Path

from kexploit_agent import HarnessType, Limits, ModelConfig
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from android_bench.catalog import ChallengeName


class BenchmarkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(min_length=1)
    num_instances: int | None = Field(default=None, ge=1)
    challenges: list[ChallengeName] | None = None
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
        cls, value: list[ChallengeName] | None
    ) -> list[ChallengeName] | None:
        if value is not None and not value:
            raise ValueError("challenges must be omitted or contain at least one challenge")
        if value is not None and len(set(value)) != len(value):
            raise ValueError("challenges contains duplicate names")
        return value

    @classmethod
    def from_file(cls, path: Path) -> BenchmarkConfig:
        return cls.model_validate_json(path.read_text())

    def formatted_json(self) -> str:
        return json.dumps(self.model_dump(mode="json", by_alias=True), indent=2) + "\n"
