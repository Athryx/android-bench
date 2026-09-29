from __future__ import annotations

import logging
from contextlib import suppress
from typing import Self

from kbench import AdbSandbox, GlobalRunState
from ksandbox import DockerSandbox, MountInfo

logger = logging.getLogger(__name__)

GUEST_ADB_HOST = "cuttlefish"
GUEST_ADB_PORT = 6000


class AndroidBenchSandbox(AdbSandbox):
    """KBench ADB sandbox with support for adopting an existing Docker sandbox."""

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
        apps_to_install: tuple[str, ...] = (),
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
        self.apps_to_install = apps_to_install

    @property
    def load_template_apps(self) -> bool:
        return True

    def _after_adb_connect(self) -> None:
        if not self.apps_to_install:
            return
        if self.sandbox is None:
            raise RuntimeError("cannot install apps without a running container")
        prefix = f"Challenge '{self.name}': " if self.name else ""
        for apk_path in self.apps_to_install:
            logger.info("%sinstalling app on Cuttlefish (apk=%s)", prefix, apk_path)
            result = self.sandbox.exec_sync(
                ["adb", "-s", self.container_adb_host, "install", "-r", "-g", apk_path],
                timeout_secs=120,
            )
            if result.exit_code != 0:
                output = (result.stdout + result.stderr).decode(errors="replace").strip()
                raise RuntimeError(f"failed to install {apk_path}: {output}")
            logger.info("%sapp installed on Cuttlefish (apk=%s)", prefix, apk_path)

    def start(self) -> Self:
        with self._lifecycle_lock:
            if self._started:
                return self
            if self._stopped or self._starting:
                raise RuntimeError("cannot restart a stopped or starting AdbSandbox")
            self._starting = True
        self.state.register_sandbox(self)

        prefix = f"Challenge '{self.name}': " if self.name else ""
        logger.info(
            "%sstarting Cuttlefish (template=%s)", prefix, self.cuttle_template
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

                logger.info(
                    "%sCuttlefish ready (instance=%s, adb=%s)",
                    prefix,
                    self.cuttle_cli_device_id,
                    cuttle_result.adb_target,
                )
                if self.existing_sandbox is None:
                    logger.info("%sstarting container (image=%s)", prefix, self.docker_tag)
                    extra_hosts = dict(self.extra_hosts)
                    extra_hosts[GUEST_ADB_HOST] = "127.0.0.1"
                    self.sandbox = self.state.sandbox_provider.create(
                        self.docker_tag,
                        mounts=self.mounts,
                        allow_internet=self.internet_enabled,
                        extra_hosts=extra_hosts,
                    )
                    self.sandbox.start()
                else:
                    logger.info("%sattaching existing container", prefix)
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
            logger.info("%scontainer ready (adb=%s)", prefix, self.container_adb_host)
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
