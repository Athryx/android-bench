from __future__ import annotations

from kbench import AdbSandbox

GUEST_ADB_HOST = "cuttlefish"
GUEST_ADB_PORT = 6000
APP_INSTALL_TIMEOUT_SECONDS = 900
ADB_COMMAND_TIMEOUT_SECONDS = 60


class AndroidBenchSandbox(AdbSandbox):
    """KBench ADB sandbox that provisions the benchmark apps after forwarding ADB."""

    @property
    def load_template_apps(self) -> bool:
        return False

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

    def _after_adb_connect(self) -> None:
        self._stabilize_device()
        assert self.sandbox is not None
        installed = self.sandbox.exec_sync(
            ["android-bench-install-apps", self.container_adb_host],
            timeout_secs=APP_INSTALL_TIMEOUT_SECONDS,
        )
        if installed.exit_code != 0:
            raise RuntimeError(
                "failed to install benchmark apps: "
                + installed.stderr.decode("utf-8", errors="replace")
            )
