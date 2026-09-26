from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest
from kbench import GlobalRunState
from ksandbox import DockerSandbox

from android_bench.sandbox import AndroidBenchSandbox


class _Container:
    def __init__(self) -> None:
        self.running = True
        self.stopped = False
        self.commands: list[list[str]] = []

    def stop(self) -> None:
        self.stopped = True
        self.running = False

    def exec_sync(
        self, command: list[str], *, timeout_secs: int
    ) -> SimpleNamespace:
        self.commands.append(command)
        return SimpleNamespace(exit_code=0, stdout=b"", stderr=b"")


class _CuttleClient:
    def __init__(self, visible_ids: tuple[str, ...] = ()) -> None:
        self.visible_ids = visible_ids

    def stop(self, instance_id: str) -> None:
        raise RuntimeError("server reported force-stop timeout")

    def list_instances(self) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(instance_id=value, instance_name=f"name-{value}")
            for value in self.visible_ids
        ]


def _sandbox(cuttle_client: _CuttleClient) -> AndroidBenchSandbox:
    state = MagicMock(spec=GlobalRunState)
    state.cuttle_client = cuttle_client
    sandbox = AndroidBenchSandbox(state, "android-bench:test", "challenge6", [])
    sandbox._started = True
    sandbox.cuttle_cli_device_id = "instance-1"
    sandbox.sandbox = cast(DockerSandbox, _Container())
    return sandbox


def test_stop_accepts_force_stop_error_after_instance_disappears() -> None:
    sandbox = _sandbox(_CuttleClient())

    sandbox.stop()

    assert sandbox._stopped
    assert cast(_Container, sandbox.sandbox).stopped


def test_stop_reraises_when_instance_is_still_visible() -> None:
    sandbox = _sandbox(_CuttleClient(("instance-1",)))

    with pytest.raises(RuntimeError, match="force-stop timeout"):
        sandbox.stop()


def test_start_enables_solver_internet_when_requested() -> None:
    container = MagicMock()
    container.running = True
    container.exec_sync.return_value = SimpleNamespace(
        exit_code=0,
        stdout=b"",
        stderr=b"",
    )
    provider = MagicMock()
    provider.create.return_value = container
    cuttle_client = MagicMock()
    cuttle_client.start.return_value = SimpleNamespace(
        adb_target="adb.internal:6520",
        instance=SimpleNamespace(instance_id="instance-1"),
    )
    state = MagicMock(spec=GlobalRunState)
    state.sandbox_provider = provider
    state.cuttle_client = cuttle_client
    sandbox = AndroidBenchSandbox(
        state,
        "android-bench:test",
        "challenge6",
        [],
        internet_enabled=True,
    )

    sandbox.start()

    provider.create.assert_called_once_with(
        "android-bench:test",
        mounts=[],
        allow_internet=True,
        extra_hosts={"cuttlefish": "127.0.0.1"},
    )
    cuttle_client.start.assert_called_once_with(
        "challenge6",
        name=sandbox.cuttle_cli_instance_name,
        load_apps=True,
        unmanaged=True,
    )


def test_after_adb_connect_installs_grader_and_challenge_app() -> None:
    container = MagicMock()
    container.exec_sync.return_value = SimpleNamespace(exit_code=0, stdout=b"", stderr=b"")
    sandbox = AndroidBenchSandbox(
        MagicMock(spec=GlobalRunState), "android-bench:test", "challenge6", []
    )
    sandbox.sandbox = container

    sandbox._after_adb_connect()

    assert container.exec_sync.call_count == 2
    first_call_cmd = container.exec_sync.call_args_list[0][0][0]
    second_call_cmd = container.exec_sync.call_args_list[1][0][0]
    assert "/opt/android-bench/grader.apk" in first_call_cmd[2]
    assert "/challenge/*.apk" in second_call_cmd[2]

