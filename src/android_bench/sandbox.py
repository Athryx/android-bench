from __future__ import annotations

from kbench import AdbSandbox

GUEST_ADB_HOST = "cuttlefish"
GUEST_ADB_PORT = 6000
GRADER_APK_PATH = "/opt/android-bench/grader.apk"
APP_INSTALL_TIMEOUT_SECONDS = 120


class AndroidBenchSandbox(AdbSandbox):
    """KBench ADB sandbox that provisions the grader and test apps after forwarding ADB."""

    @property
    def load_template_apps(self) -> bool:
        return True

    def _after_adb_connect(self) -> None:
        assert self.sandbox is not None
        installed_grader = self.sandbox.exec_sync(
            [
                "sh",
                "-c",
                f'if [ -f "{GRADER_APK_PATH}" ]; then adb -s "{self.container_adb_host}" install -r -g "{GRADER_APK_PATH}"; fi',
            ],
            timeout_secs=APP_INSTALL_TIMEOUT_SECONDS,
        )
        if installed_grader.exit_code != 0:
            raise RuntimeError(
                "failed to install grader app: "
                + installed_grader.stderr.decode("utf-8", errors="replace")
            )

        installed_challenge = self.sandbox.exec_sync(
            [
                "sh",
                "-c",
                f'for apk in /challenge/*.apk; do [ -f "$apk" ] && adb -s "{self.container_adb_host}" install -r -g "$apk"; done',
            ],
            timeout_secs=APP_INSTALL_TIMEOUT_SECONDS,
        )
        if installed_challenge.exit_code != 0:
            raise RuntimeError(
                "failed to install challenge app: "
                + installed_challenge.stderr.decode("utf-8", errors="replace")
            )
