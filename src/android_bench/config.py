from __future__ import annotations

import json
from pathlib import Path

from kexploit_agent import HarnessType, ModelConfig
from pydantic import BaseModel, ConfigDict, Field, field_validator

from android_bench.catalog import ChallengeName


class BenchmarkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(min_length=1)
    num_instances: int | None = Field(default=None, ge=1)
    challenges: list[ChallengeName] | None = None
    harness: HarnessType
    agent_model_config: ModelConfig = Field(alias="model_config")
    max_reprompts: int = Field(default=2, ge=0)

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
