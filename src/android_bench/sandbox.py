from __future__ import annotations

import logging
from contextlib import suppress
from typing import Self

from kbench import AdbSandbox

GUEST_ADB_HOST = "cuttlefish"
GUEST_ADB_PORT = 6000
APP_INSTALL_TIMEOUT_SECONDS = 900
ADB_COMMAND_TIMEOUT_SECONDS = 60
logger = logging.getLogger(__name__)


class AndroidBenchSandbox(AdbSandbox):
    """KBench ADB sandbox that provisions the benchmark apps after forwarding ADB."""

    def _exec_checked_adb(self, *args: str, description: str) -> None:
        assert self.sandbox is not None
        result = self.sandbox.exec_sync(
            ["adb", "-s", self.container_adb_host, *args],
            timeout_secs=ADB_COMMAND_TIMEOUT_SECONDS,
        )
        if result.exit_code != 0:
            output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
            raise RuntimeError(f"{description} failed: {output}")

    def _stabilize_device(self) -> None:
        """Disable guest networking before its NetworkMonitor receiver leak fires.

        The Challenge 6.1 image repeatedly creates and removes its virtual Ethernet
        network when booted normally. Each NetworkMonitor instance leaks a broadcast
        receiver and system_server dies at the 1,000-receiver process limit. Using
        ConnectivityService's command (rather than only changing the global setting)
        tears down the provider and also enforces the benchmark's offline boundary.
        """

        self._exec_checked_adb("root", description="restarting adbd as root")
        self._exec_checked_adb("wait-for-device", description="waiting for rooted adbd")
        self._exec_checked_adb(
            "shell",
            "cmd",
            "connectivity",
            "airplane-mode",
            "enable",
            description="enabling guest airplane mode",
        )
        self._exec_checked_adb(
            "shell",
            "svc",
            "wifi",
            "disable",
            description="disabling guest Wi-Fi",
        )
        self._exec_checked_adb(
            "shell",
            "svc",
            "data",
            "disable",
            description="disabling guest mobile data",
        )

    def start(self) -> Self:
        if self._started:
            return self
        if self._stopped:
            raise RuntimeError("cannot restart a stopped AndroidBenchSandbox")

        cuttle_result = self.state.cuttle_client.start(
            self.cuttle_template,
            load_apps=False,
            unmanaged=True,
        )
        if cuttle_result.adb_target is None:
            raise RuntimeError("Cuttlefish server did not return an ADB target")
        self.adb_host, port_str = cuttle_result.adb_target.split(":")
        self.adb_port = int(port_str)
        self.cuttle_cli_device_id = cuttle_result.instance.instance_id

        try:
            extra_hosts = dict(self.extra_hosts)
            extra_hosts[GUEST_ADB_HOST] = "127.0.0.1"
            self.sandbox = self.state.sandbox_provider.create(
                self.docker_tag,
                mounts=self.mounts,
                allow_internet=self.internet_enabled,
                extra_hosts=extra_hosts,
            )
            self.sandbox.start()
            self.sandbox.forward_port(
                target_host=self.adb_host,
                host_port=self.adb_port,
                guest_addr="127.0.0.1",
                guest_port=GUEST_ADB_PORT,
            )
            connected = self.sandbox.exec_sync(
                ["adb", "connect", self.container_adb_host], timeout_secs=60
            )
            if connected.exit_code != 0:
                raise RuntimeError(
                    f"failed to connect sandbox ADB: {connected.stderr.decode(errors='replace')}"
                )
            self._stabilize_device()
            installed = self.sandbox.exec_sync(
                ["android-bench-install-apps", self.container_adb_host],
                timeout_secs=APP_INSTALL_TIMEOUT_SECONDS,
            )
            if installed.exit_code != 0:
                raise RuntimeError(
                    "failed to install benchmark apps: "
                    + installed.stderr.decode("utf-8", errors="replace")
                )
        except Exception:
            if self.sandbox is not None and self.sandbox.running:
                with suppress(Exception):
                    self.sandbox.stop()
            try:
                self.state.cuttle_client.stop(self.cuttle_cli_device_id)
            except Exception:
                logger.warning(
                    "failed to stop Cuttlefish instance after sandbox startup error",
                    exc_info=True,
                )
            raise

        self._started = True
        return self

    def stop(self) -> None:
        if self._stopped or not self._started:
            return
        self._stopped = True
        try:
            if self.sandbox is not None and self.sandbox.running:
                self.sandbox.stop()
        finally:
            if self.cuttle_cli_device_id is not None:
                try:
                    self.state.cuttle_client.stop(self.cuttle_cli_device_id)
                except Exception as stop_error:
                    try:
                        still_visible = any(
                            instance.instance_id == self.cuttle_cli_device_id
                            for instance in self.state.cuttle_client.list_instances()
                        )
                    except Exception as verification_error:
                        raise stop_error from verification_error
                    if still_visible:
                        raise
                    logger.info(
                        "Cuttlefish stop reported an error after the instance disappeared: %s",
                        str(stop_error).splitlines()[0],
                    )
