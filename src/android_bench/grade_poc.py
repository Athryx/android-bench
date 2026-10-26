"""Run one deterministic capability against an existing, disposable ADB device."""

from __future__ import annotations

import os
import signal
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

from ksandbox import ExecResult
from pydantic import BaseModel, ConfigDict, Field

from android_bench.docker import grader_apk_path
from android_bench.grader import GRADERS, DeterministicGrader
from android_bench.models import Capability, CapabilityResult


class PocTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")


class LocalExecutor:
    def exec_sync(
        self,
        cmd: list[str],
        /,
        *,
        cwd: str | None = None,
        timeout_secs: float = 60,
    ) -> ExecResult:
        with subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        ) as process:
            try:
                stdout, stderr = process.communicate(timeout=timeout_secs)
            except BaseException as error:
                # Kill the whole group, including helpers spawned by a PoC script.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.communicate()
                if isinstance(error, subprocess.TimeoutExpired):
                    raise TimeoutError(f"command exceeded {timeout_secs}s") from error
                raise
            return ExecResult(stdout=stdout, stderr=stderr, exit_code=process.returncode)


@dataclass(frozen=True)
class LocalAdbSandbox:
    container_adb_host: str
    sandbox: LocalExecutor


def run_grade_poc(adb_target: str, capability: Capability, poc: Path) -> CapabilityResult:
    poc = poc.resolve()
    if not poc.is_file() or not os.access(poc, os.X_OK):
        raise ValueError(f"PoC must be an executable file: {poc}")
    config_path = poc.parent / "grade-poc.toml"
    with config_path.open("rb") as config_file:
        target = PocTarget.model_validate(tomllib.load(config_file))

    apk = grader_apk_path()
    if not apk.is_file():
        raise ValueError(f"Grader APK missing at {apk}; run 'android-bench setup' first")
    executor = LocalExecutor()
    grader = DeterministicGrader(
        LocalAdbSandbox(container_adb_host=adb_target, sandbox=executor),
        target,
        grader_apk=str(apk),
        poc_path=str(poc),
    )
    grader.adb("connect", adb_target)
    grader.prepare()
    return grader.grade_all((GRADERS[capability],))[capability]
