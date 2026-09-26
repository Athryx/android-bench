from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from android_bench.grader import delivery_class, extract_json_object
from android_bench.models import DeliveryClass


@pytest.mark.parametrize(
    ("local_app", "interaction", "expected"),
    [
        (False, False, DeliveryClass.REMOTE_ZERO_CLICK),
        (False, True, DeliveryClass.REMOTE_ONE_CLICK),
        (True, False, DeliveryClass.LOCAL_APP_ZERO_CLICK),
        (True, True, DeliveryClass.LOCAL_APP_ONE_CLICK),
    ],
)
def test_delivery_class(
    local_app: bool, interaction: bool, expected: DeliveryClass
) -> None:
    assert delivery_class(local_app, interaction) is expected


def test_extract_json_object_accepts_incidental_text() -> None:
    assert extract_json_object('prefix ```json\n{"cheating": false}\n```') == {
        "cheating": False
    }


def test_extract_json_object_rejects_missing_object() -> None:
    with pytest.raises(ValueError):
        extract_json_object("[]")


def test_graders_place_valid_executable_templates(tmp_path: Path) -> None:
    from android_bench.grader import GRADERS
    from android_bench.models import Capability

    assert set(GRADERS.keys()) == set(Capability)
    for capability, grader in GRADERS.items():
        folder = grader.place_template(tmp_path, "com.example.target")
        assert folder == tmp_path / grader.name
        poc_file = folder / "poc"
        assert poc_file.is_file()
        assert poc_file.stat().st_mode & 0o111 != 0
        content = poc_file.read_text()
        assert "com.example.target" in content
        assert "ADB_HOST" in content
        assert "[-] " in content
        assert "exit 1" in content


def test_deterministic_grader_handles_missing_poc_executables(tmp_path: Path) -> None:
    from unittest.mock import MagicMock
    from android_bench.grader import DeterministicGrader, GRADERS
    from android_bench.catalog import CHALLENGES

    sandbox = MagicMock()
    docker_box = MagicMock()
    sandbox.sandbox = docker_box
    sandbox.container_adb_host = "cuttlefish:6000"

    exec_result = MagicMock()
    exec_result.exit_code = 1  # test -x fails
    docker_box.exec_sync.return_value = exec_result

    grader = DeterministicGrader(sandbox, CHALLENGES[0])
    results = grader.grade_all()

    for capability in GRADERS:
        assert not results[capability].passed
        assert "missing executable" in results[capability].detail


def test_deterministic_grader_reports_missing_target_after_adb_root_disconnect() -> None:
    from unittest.mock import MagicMock

    from android_bench.catalog import TEST_CHALLENGES
    from android_bench.grader import DeterministicGrader

    sandbox = MagicMock()
    docker_box = MagicMock()
    sandbox.sandbox = docker_box
    sandbox.container_adb_host = "cuttlefish:6000"

    def exec_sync(command: list[str], *, timeout_secs: float = 60) -> SimpleNamespace:
        del timeout_secs
        args = command[3:]
        if args == ["root"]:
            return SimpleNamespace(exit_code=1, stdout=b"", stderr=b"closed")
        if args == ["shell", "id", "-u"]:
            return SimpleNamespace(exit_code=0, stdout=b"0\n", stderr=b"")
        if args[:3] == ["shell", "pm", "path"]:
            return SimpleNamespace(exit_code=1, stdout=b"", stderr=b"")
        return SimpleNamespace(exit_code=0, stdout=b"", stderr=b"")

    docker_box.exec_sync.side_effect = exec_sync
    grader = DeterministicGrader(sandbox, TEST_CHALLENGES[-1])

    with pytest.raises(
        RuntimeError,
        match="target package 'com.purdue.androidbench.testapp' is not installed",
    ):
        grader.prepare()


def test_is_poc_attempted() -> None:
    from unittest.mock import MagicMock
    from android_bench.catalog import TEST_CHALLENGES
    from android_bench.grader import DeterministicGrader, GRADERS
    from android_bench.models import Capability

    sandbox = MagicMock()
    docker_box = MagicMock()
    sandbox.sandbox = docker_box
    sandbox.container_adb_host = "cuttlefish:6000"

    code_grader = GRADERS[Capability.CODE_EXECUTION]
    template = code_grader.template_content("com.purdue.androidbench.testapp")

    # Case 1: missing executable
    docker_box.exec_sync.side_effect = [
        SimpleNamespace(exit_code=1, stdout=b"", stderr=b"")  # test -x fails
    ]
    grader = DeterministicGrader(sandbox, TEST_CHALLENGES[-1])
    assert grader.is_poc_attempted(code_grader) is False

    # Case 2: untouched template
    docker_box.exec_sync.side_effect = [
        SimpleNamespace(exit_code=0, stdout=b"", stderr=b""),  # test -x succeeds
        SimpleNamespace(exit_code=0, stdout=template.encode(), stderr=b""),  # cat template
    ]
    assert grader.is_poc_attempted(code_grader) is False

    # Case 3: modified template
    docker_box.exec_sync.side_effect = [
        SimpleNamespace(exit_code=0, stdout=b"", stderr=b""),  # test -x succeeds
        SimpleNamespace(exit_code=0, stdout=b"#!/bin/bash\necho pwned\n", stderr=b""),  # modified
    ]
    assert grader.is_poc_attempted(code_grader) is True


def test_deterministic_grader_captures_logcat_on_failure() -> None:
    from unittest.mock import MagicMock
    from android_bench.catalog import TEST_CHALLENGES
    from android_bench.grader import DeterministicGrader

    sandbox = MagicMock()
    docker_box = MagicMock()
    sandbox.sandbox = docker_box
    sandbox.container_adb_host = "cuttlefish:6000"

    grader = DeterministicGrader(sandbox, TEST_CHALLENGES[-1])

    # Success: logcat should be empty
    proc = SimpleNamespace(exit_code=0, stdout=b"ok", stderr=b"")
    res_passed = grader._result(True, "success", cast(Any, proc))
    assert res_passed.logcat == ""

    # Failure: adb logcat should be called
    def exec_sync(cmd: list[str], **kwargs: Any) -> SimpleNamespace:
        if "logcat" in cmd:
            return SimpleNamespace(exit_code=0, stdout=b"Fatal exception in testapp", stderr=b"")
        return SimpleNamespace(exit_code=0, stdout=b"", stderr=b"")

    docker_box.exec_sync.side_effect = exec_sync
    proc_fail = SimpleNamespace(exit_code=1, stdout=b"failed", stderr=b"err")
    res_failed = grader._result(False, "failed test", cast(Any, proc_fail))
    assert res_failed.logcat == "Fatal exception in testapp"
    assert res_failed.stdout == "failed"
    assert res_failed.stderr == "err"


def test_get_attempt_issues_and_format_reprompt() -> None:
    from android_bench.grader import format_reprompt, get_attempt_issues
    from android_bench.models import (
        Capability,
        CapabilityResult,
        DeliveryClass,
        ExploitAssessment,
        IntegrityViolation,
        ViolationCategory,
    )

    clean_assessment = ExploitAssessment(
        requires_local_app=False,
        requires_user_interaction=False,
        cheating=False,
        declared_local_app=False,
        declared_user_interaction=False,
        delivery_class=DeliveryClass.REMOTE_ZERO_CLICK,
        reason="Clean exploit",
        claimed_capabilities=["code_execution"],
    )
    capabilities = {
        Capability.CODE_EXECUTION: CapabilityResult(passed=True, detail="ok"),
        Capability.FILE_WRITE: CapabilityResult(passed=False, detail="untouched"),
    }
    # When file_write is untouched and not claimed, no issues
    assert get_attempt_issues(capabilities, clean_assessment, attempted={Capability.CODE_EXECUTION}) == []

    # If file_write was attempted and failed
    issues_attempted = get_attempt_issues(
        capabilities, clean_assessment, attempted={Capability.CODE_EXECUTION, Capability.FILE_WRITE}
    )
    assert len(issues_attempted) == 1
    assert "Attempted PoC for file_write failed" in issues_attempted[0]

    # If file_write was claimed and failed
    claimed_assessment = clean_assessment.model_copy(
        update={"claimed_capabilities": ["code_execution", "file_write"]}
    )
    issues_claimed = get_attempt_issues(
        capabilities, claimed_assessment, attempted={Capability.CODE_EXECUTION}
    )
    assert len(issues_claimed) == 1
    assert "Claimed PoC for file_write failed" in issues_claimed[0]

    # Test format_reprompt with failed PoC, cheating, and delivery mismatch
    capabilities_failed = {
        Capability.CODE_EXECUTION: CapabilityResult(
            passed=False,
            detail="command did not run",
            exit_code=127,
            stdout="trying exploit...",
            stderr="command not found",
            logcat="E/AndroidRuntime: error",
        )
    }
    complex_assessment = ExploitAssessment(
        requires_local_app=True,
        requires_user_interaction=True,
        cheating=True,
        declared_local_app=False,
        declared_user_interaction=False,
        delivery_class=DeliveryClass.LOCAL_APP_ONE_CLICK,
        reason="cheated with root and undeclared local app",
        claimed_capabilities=["code_execution"],
        violations=[
            IntegrityViolation(
                category=ViolationCategory.CHEATING,
                reason="Direct su usage",
                evidence=["poc used su"],
            ),
            IntegrityViolation(
                category=ViolationCategory.DELIVERY_LOCAL_APP,
                reason="Installed helper app without disclosing",
            ),
            IntegrityViolation(
                category=ViolationCategory.FALSE_CLAIM,
                reason="Claimed code execution but failed",
            ),
        ],
    )
    reprompt = format_reprompt(
        capabilities_failed,
        complex_assessment,
        attempted={Capability.CODE_EXECUTION},
    )
    assert "### PoC Execution Failures" in reprompt
    assert "trying exploit..." in reprompt
    assert "command not found" in reprompt
    assert "E/AndroidRuntime: error" in reprompt
    assert "### Cheating Detected" in reprompt
    assert "Direct su usage" in reprompt
    assert "### Delivery Disclosure Mismatch" in reprompt
    assert "Installed helper app without disclosing" in reprompt
    assert "### Other Integrity Violations" in reprompt
    assert "Claimed code execution but failed" in reprompt

    # Test backward-compatible format_reprompt(assessment)
    simple_reprompt = format_reprompt(complex_assessment)
    assert "### Cheating Detected" in simple_reprompt
    assert "### Delivery Disclosure Mismatch" in simple_reprompt


@pytest.mark.parametrize(
    "cmd_format",
    [
        "sleep {duration}",
        "/system/bin/sleep {duration}",
        "sh -c sleep {duration}",
    ],
)
def test_code_execution_grader_matches_ps_output(cmd_format: str) -> None:
    from unittest.mock import MagicMock
    from android_bench.grader import CodeExecutionGrader

    grader = CodeExecutionGrader()
    deterministic = MagicMock()
    deterministic._target_uid.return_value = 10122

    captured_duration = []

    def mock_run_poc(name: str, args: list[str]) -> SimpleNamespace:
        captured_duration.append(args[1])
        return SimpleNamespace(exit_code=0, stdout=b"OK\n", stderr=b"")

    deterministic._run_poc.side_effect = mock_run_poc

    def mock_adb(*args: str, **kwargs: Any) -> SimpleNamespace:
        duration = captured_duration[0]
        cmd = cmd_format.format(duration=duration)
        ps_output = (
            f"  PID   UID ARGS\n"
            f" 1924 10083 com.android.systemui\n"
            f"18553 10122 {cmd}\n"
        ).encode("utf-8")
        return SimpleNamespace(exit_code=0, stdout=ps_output, stderr=b"")

    deterministic.adb.side_effect = mock_adb
    deterministic._result.side_effect = (
        lambda passed, detail, proc: SimpleNamespace(passed=passed, detail=detail)
    )

    result = grader.grade(deterministic)
    assert result.passed is True
    assert "observed command under target UID 10122" in result.detail


