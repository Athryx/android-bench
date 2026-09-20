from pathlib import Path
from types import SimpleNamespace

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
