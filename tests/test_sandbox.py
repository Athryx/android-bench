from __future__ import annotations

from types import SimpleNamespace

import pytest

from android_bench.sandbox import AndroidBenchSandbox


class _Container:
    def __init__(self) -> None:
        self.running = True
        self.stopped = False
        self.commands: list[list[str]] = []

    def stop(self) -> None:
        self.stopped = True
        self.running = False

    def exec_sync(self, command: list[str], *, timeout_secs: int):
        self.commands.append(command)
        return SimpleNamespace(exit_code=0, stdout=b"", stderr=b"")


class _CuttleClient:
    def __init__(self, visible_ids: tuple[str, ...] = ()) -> None:
        self.visible_ids = visible_ids

    def stop(self, instance_id: str) -> None:
        raise RuntimeError("server reported force-stop timeout")

    def list_instances(self):
        return [SimpleNamespace(instance_id=value) for value in self.visible_ids]


def _sandbox(cuttle_client: _CuttleClient) -> AndroidBenchSandbox:
    sandbox = object.__new__(AndroidBenchSandbox)
    sandbox._started = True
    sandbox._stopped = False
    sandbox.cuttle_cli_device_id = "instance-1"
    sandbox.sandbox = _Container()
    sandbox.state = SimpleNamespace(cuttle_client=cuttle_client)
    return sandbox


def test_stop_accepts_force_stop_error_after_instance_disappears() -> None:
    sandbox = _sandbox(_CuttleClient())

    sandbox.stop()

    assert sandbox._stopped
    assert sandbox.sandbox.stopped


def test_stop_reraises_when_instance_is_still_visible() -> None:
    sandbox = _sandbox(_CuttleClient(("instance-1",)))

    with pytest.raises(RuntimeError, match="force-stop timeout"):
        sandbox.stop()


def test_stabilize_device_enables_airplane_mode_before_provisioning() -> None:
    sandbox = _sandbox(_CuttleClient())

    sandbox._stabilize_device()

    assert sandbox.sandbox.commands == [
        ["adb", "-s", "cuttlefish:6000", "root"],
        ["adb", "-s", "cuttlefish:6000", "wait-for-device"],
        [
            "adb",
            "-s",
            "cuttlefish:6000",
            "shell",
            "cmd",
            "connectivity",
            "airplane-mode",
            "enable",
        ],
        ["adb", "-s", "cuttlefish:6000", "shell", "svc", "wifi", "disable"],
        ["adb", "-s", "cuttlefish:6000", "shell", "svc", "data", "disable"],
    ]
