from __future__ import annotations

from kbench import AdbSandbox

GUEST_ADB_HOST = "cuttlefish"
GUEST_ADB_PORT = 6000
APP_INSTALL_TIMEOUT_SECONDS = 900


class AndroidBenchSandbox(AdbSandbox):
    """KBench ADB sandbox that provisions the benchmark apps after forwarding ADB."""

    @property
    def load_template_apps(self) -> bool:
        return False

    def _after_adb_connect(self) -> None:
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
