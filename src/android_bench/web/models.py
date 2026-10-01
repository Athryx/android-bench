from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class TreeNode(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["folder", "run"]
    name: str
    display_name: str
    path: str
    full_path: str
    started_at: str | None = None
    started_timestamp: float | None = None
    score: float | None = None
    status: str | None = None
    children: list[TreeNode] = Field(default_factory=list)


class TreeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    root_path: str
    items: list[TreeNode] = Field(default_factory=list)


class CapabilityDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    passed: bool = False
    detail: str = ""
    score: float = 0.0
    weight: float = 0.0
    stdout: str = ""
    stderr: str = ""
    logcat: str = ""
    exit_code: int | None = None
    attempted: bool = True
    cheating: bool | None = None
    requires_local_app: bool | None = None
    requires_user_interaction: bool | None = None
    declared_local_app: bool | None = None
    declared_user_interaction: bool | None = None
    has_integrity_issue: bool = False
    reasoning: str = ""


class AttemptDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    attempt: int
    response: str = ""
    reprompt: str | None = None
    capabilities: dict[str, CapabilityDetail] = Field(default_factory=dict)


class ChallengeDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    package: str = ""
    status: str = "completed"
    score: float = 0.0
    runtime: float = 0.0
    session_id: str | None = None
    trace_url: str | None = None
    axes: dict[str, float] = Field(default_factory=dict)
    enabled_capabilities: list[str] = Field(default_factory=list)
    attempts: list[AttemptDetail] = Field(default_factory=list)
    limit_exceeded: str | None = None
    error: str | None = None


class RunConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    model: str = ""
    model_effort: str = ""
    harness: str = ""
    num_instances: int | None = None
    internet_enabled: bool | None = None
    summarize: bool | None = None
    max_reprompts: int | None = None
    time_limit: float | None = None
    raw_toml: str = ""


class RunDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: str
    full_path: str
    folder_name: str
    challenge_name: str = ""
    display_name: str = ""
    started_at: str = ""
    started_timestamp: float | None = None
    score: float = 0.0
    total_runtime: float = 0.0
    status: str = "completed"
    notes: str | None = None
    config: RunConfig = Field(default_factory=RunConfig)
    challenges: list[ChallengeDetail] = Field(default_factory=list)


class WebConfigResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    results_dir: str
    kagent_web_host: str
