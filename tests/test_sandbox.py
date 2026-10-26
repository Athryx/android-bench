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


@pytest.mark.parametrize("load_template_apps", [True, False])
def test_start_enables_solver_internet_when_requested(
    caplog: pytest.LogCaptureFixture,
    load_template_apps: bool,
) -> None:
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
        load_template_apps=load_template_apps,
    )

    with caplog.at_level("INFO", logger="android_bench.sandbox"):
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
        load_apps=load_template_apps,
        unmanaged=True,
    )
    assert all(
        "grader.apk" not in " ".join(call.args[0])
        for call in container.exec_sync.call_args_list
    )
    messages = [record.message for record in caplog.records]
    assert messages == [
        "starting Cuttlefish (template=challenge6)",
        "Cuttlefish ready (instance=instance-1, adb=adb.internal:6520)",
        "starting container (image=android-bench:test)",
        "container ready (adb=cuttlefish:6000)",
    ]


def test_start_installs_only_catalog_requested_apps(
    caplog: pytest.LogCaptureFixture,
) -> None:
    container = MagicMock()
    container.running = True
    container.exec_sync.return_value = SimpleNamespace(
        exit_code=0, stdout=b"Success\n", stderr=b""
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
        name="test_all",
        apps_to_install=("/challenge/test_app.apk",),
    )

    with caplog.at_level("INFO", logger="android_bench.sandbox"):
        sandbox.start()

    container.exec_sync.assert_any_call(
        [
            "adb", "-s", "cuttlefish:6000", "install", "-r", "-g",
            "/challenge/test_app.apk",
        ],
        timeout_secs=120,
    )
    assert "Challenge 'test_all': app installed on Cuttlefish (apk=/challenge/test_app.apk)" in [
        record.message for record in caplog.records
    ]


def test_requested_app_installation_failure_is_reported() -> None:
    sandbox = AndroidBenchSandbox(
        MagicMock(spec=GlobalRunState),
        "android-bench:test",
        "challenge6",
        [],
        apps_to_install=("/challenge/test_app.apk",),
    )
    container = MagicMock()
    container.exec_sync.return_value = SimpleNamespace(
        exit_code=1,
        stdout=b"",
        stderr=b"INSTALL_FAILED_INVALID_APK",
    )
    sandbox.sandbox = container

    with pytest.raises(RuntimeError, match="INSTALL_FAILED_INVALID_APK"):
        sandbox._after_adb_connect()


@pytest.mark.parametrize("suffix", [".apkm", ".xapk", ".XAPK"])
def test_archive_installation_uses_bundled_installer(suffix: str) -> None:
    app_path = f"/challenge/target{suffix}"
    sandbox = AndroidBenchSandbox(
        MagicMock(spec=GlobalRunState),
        "android-bench:test",
        "custom-template",
        [],
        apps_to_install=(app_path,),
    )
    container = MagicMock()
    container.exec_sync.return_value = SimpleNamespace(
        exit_code=0, stdout=b"Success\n", stderr=b""
    )
    sandbox.sandbox = container

    sandbox._after_adb_connect()

    assert sandbox.load_template_apps is True
    container.exec_sync.assert_called_once_with(
        ["/usr/local/bin/android-bench-install-apps", "cuttlefish:6000", app_path],
        timeout_secs=120,
    )
