from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from ksandbox import ExecResult
from typer.testing import CliRunner

from android_bench.cli import app
from android_bench.grade_poc import LocalExecutor, run_grade_poc
from android_bench.grader import GRADERS, DeterministicGrader
from android_bench.models import Capability, CapabilityResult


@pytest.fixture
def poc(tmp_path: Path) -> Path:
    executable = tmp_path / "custom-poc"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    (tmp_path / "grade-poc.toml").write_text('package = "com.example.target"\n')
    return executable


@pytest.mark.parametrize("capability", list(Capability))
def test_standalone_grades_only_requested_capability(
    monkeypatch: pytest.MonkeyPatch, poc: Path, capability: Capability,
) -> None:
    apk = poc.parent / "grader.apk"
    apk.write_bytes(b"apk")
    monkeypatch.setattr("android_bench.grade_poc.grader_apk_path", lambda: apk)
    commands: list[list[str]] = []

    def execute(
        self: LocalExecutor, cmd: list[str], /, *,
        cwd: str | None = None, timeout_secs: float = 60,
    ) -> ExecResult:
        commands.append(cmd)
        if cmd == [str(poc), "localhost:6520", "argument with spaces"]:
            assert cwd == str(poc.parent)
            assert timeout_secs == 300
            return ExecResult(stdout=b"proof", stderr=b"diagnostic", exit_code=0)
        assert cwd is None
        if cmd[-1] == "root":
            return ExecResult(stdout=b"", stderr=b"closed", exit_code=1)
        output = b""
        if cmd[3:] == ["shell", "id", "-u"]:
            output = b"0\n"
        elif cmd[3:] == ["shell", "pm", "path", "com.example.target"]:
            output = b"package:/data/app/target/base.apk\n"
        elif cmd[3:] == ["shell", "pm", "list", "packages"]:
            output = b"package:com.example.target\n"
        return ExecResult(stdout=output, stderr=b"", exit_code=0)

    def grade(deterministic: DeterministicGrader) -> CapabilityResult:
        process = deterministic._run_poc(capability.value, ["argument with spaces"])
        return deterministic._result(True, "passed", process)

    monkeypatch.setattr(LocalExecutor, "exec_sync", execute)
    selected = Mock(side_effect=grade)
    for candidate, grader in GRADERS.items():
        monkeypatch.setattr(grader, "grade", selected if candidate == capability else Mock(
            side_effect=AssertionError("unselected grader ran"),
        ))

    result = run_grade_poc("localhost:6520", capability, poc)
    assert result.passed
    assert result.stdout == "proof"
    selected.assert_called_once()
    assert commands[0] == ["adb", "-s", "localhost:6520", "connect", "localhost:6520"]
    installs = [cmd for cmd in commands if "install" in cmd]
    assert installs == [[
        "adb", "-s", "localhost:6520", "install", "-r", "-g", "--force-queryable", str(apk),
    ]]
    assert ["adb", "-s", "localhost:6520", "shell", "pm", "clear", "com.example.target"] in commands


def test_poc_requires_executable(poc: Path) -> None:
    poc.chmod(0o644)
    with pytest.raises(ValueError, match="executable"):
        run_grade_poc("localhost:6520", Capability.FILE_READ, poc)


def test_poc_requires_target_config(poc: Path) -> None:
    (poc.parent / "grade-poc.toml").unlink()
    with pytest.raises(FileNotFoundError, match="grade-poc.toml"):
        run_grade_poc("localhost:6520", Capability.FILE_READ, poc)


@pytest.mark.parametrize("config", ['', 'package = "bad; shell"', 'package = "com.example.target"\nextra = 1'])
def test_poc_rejects_invalid_config(poc: Path, config: str) -> None:
    (poc.parent / "grade-poc.toml").write_text(config)
    with pytest.raises(ValueError):
        run_grade_poc("localhost:6520", Capability.FILE_READ, poc)


def test_poc_requires_grader_apk(monkeypatch: pytest.MonkeyPatch, poc: Path) -> None:
    monkeypatch.setattr("android_bench.grade_poc.grader_apk_path", lambda: poc.parent / "missing.apk")
    with pytest.raises(ValueError, match="Grader APK missing"):
        run_grade_poc("localhost:6520", Capability.FILE_READ, poc)


def test_local_executor_captures_output_and_working_directory(tmp_path: Path) -> None:
    result = LocalExecutor().exec_sync([
        sys.executable, "-c", "import os, sys; print(os.getcwd()); print('error', file=sys.stderr); sys.exit(7)",
    ], cwd=str(tmp_path))
    assert result.stdout.decode().strip() == str(tmp_path)
    assert result.stderr == b"error\n"
    assert result.exit_code == 7


def test_local_executor_times_out() -> None:
    with pytest.raises(TimeoutError):
        LocalExecutor().exec_sync([
            sys.executable, "-c", "import time; time.sleep(30)",
        ], timeout_secs=0.05)


@pytest.mark.parametrize("passed,exit_code", [(True, 0), (False, 1)])
def test_grade_poc_cli(
    monkeypatch: pytest.MonkeyPatch, poc: Path, passed: bool, exit_code: int,
) -> None:
    run = Mock(return_value=CapabilityResult(passed=passed, detail="test result"))
    monkeypatch.setattr("android_bench.cli.run_grade_poc", run)
    result = CliRunner().invoke(app, [
        "grade-poc", "--adb", "localhost:6520", "--capability", "file_read", "--poc", str(poc),
    ])
    assert result.exit_code == exit_code, result.output
    assert '"detail": "test result"' in result.stdout
    run.assert_called_once_with("localhost:6520", Capability.FILE_READ, poc)


def test_grade_poc_cli_reports_setup_error(monkeypatch: pytest.MonkeyPatch, poc: Path) -> None:
    monkeypatch.setattr("android_bench.cli.run_grade_poc", Mock(side_effect=RuntimeError("no device")))
    result = CliRunner().invoke(app, [
        "grade-poc", "--adb", "localhost:6520", "--capability", "file_read", "--poc", str(poc),
    ])
    assert result.exit_code == 2
    assert "Grading error: no device" in result.stderr


def test_grade_poc_cli_rejects_unknown_capability(poc: Path) -> None:
    result = CliRunner().invoke(app, [
        "grade-poc", "--adb", "localhost:6520", "--capability", "unknown", "--poc", str(poc),
    ])
    assert result.exit_code == 2
