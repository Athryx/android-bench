from __future__ import annotations

import logging
from contextlib import suppress
from typing import Self

from kbench import AdbSandbox, GlobalRunState
from ksandbox import DockerSandbox, MountInfo

logger = logging.getLogger(__name__)

GUEST_ADB_HOST = "cuttlefish"
GUEST_ADB_PORT = 6000
GRADER_APK_PATH = "/opt/android-bench/grader.apk"
APP_INSTALL_TIMEOUT_SECONDS = 120


class AndroidBenchSandbox(AdbSandbox):
    """KBench ADB sandbox that provisions the grader and test apps after forwarding ADB."""

    def __init__(
        self,
        state: GlobalRunState,
        docker_tag: str,
        cuttle_template: str,
        mounts: list[MountInfo],
        name: str | None = None,
        internet_enabled: bool = False,
        extra_hosts: dict[str, str] | None = None,
        existing_sandbox: DockerSandbox | None = None,
    ) -> None:
        super().__init__(
            state,
            docker_tag,
            cuttle_template,
            mounts,
            name=name,
            internet_enabled=internet_enabled,
            extra_hosts=extra_hosts,
        )
        self.existing_sandbox = existing_sandbox

    @property
    def load_template_apps(self) -> bool:
        return True

    def start(self) -> Self:
        if self.existing_sandbox is None:
            return super().start()

        with self._lifecycle_lock:
            if self._started:
                return self
            if self._stopped or self._starting:
                raise RuntimeError("cannot restart a stopped or starting AdbSandbox")
            self._starting = True
        self.state.register_sandbox(self)

        prefix = f"Challenge '{self.name}': " if self.name else ""
        logger.info(
            "%sstarting emulator (template: %s)...", prefix, self.cuttle_template
        )
        try:
            cuttle_result = self.state.cuttle_client.start(
                self.cuttle_template,
                name=self.cuttle_cli_instance_name,
                load_apps=self.load_template_apps,
                unmanaged=True,
            )
            if cuttle_result.adb_target is None:
                raise RuntimeError("Cuttlefish server did not return an ADB target")
            with self._lifecycle_lock:
                self.adb_host, port_str = cuttle_result.adb_target.split(":")
                self.adb_port = int(port_str)
                self.cuttle_cli_device_id = cuttle_result.instance.instance_id
                if self._cleanup_requested:
                    raise RuntimeError(
                        "sandbox cleanup requested during Cuttlefish startup"
                    )

                logger.info("%sadopting existing sandbox...", prefix)
                self.sandbox = self.existing_sandbox
                if not self.sandbox.running:
                    self.sandbox.start()

                with suppress(Exception):
                    self.sandbox.unforward_port(
                        guest_port=GUEST_ADB_PORT, guest_addr="127.0.0.1"
                    )
                self.sandbox.forward_port(
                    target_host=self.adb_host,
                    host_port=self.adb_port,
                    guest_addr="127.0.0.1",
                    guest_port=GUEST_ADB_PORT,
                )
            self._run_adb(["connect", self.container_adb_host])
            self._after_adb_connect()

            with self._lifecycle_lock:
                if self._cleanup_requested:
                    raise RuntimeError("sandbox cleanup requested during startup")
                self._started = True
                self._starting = False
        except BaseException:
            with self._lifecycle_lock:
                self._starting = False
            try:
                self.stop()
            except Exception:
                logger.exception(
                    "%sfailed to clean up sandbox after startup error", prefix
                )
            raise

        return self

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
