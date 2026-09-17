#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

APP_DIR = Path("/opt/android-bench/apps")
LANGUAGES = {
    "ar",
    "de",
    "en",
    "es",
    "fr",
    "hi",
    "in",
    "it",
    "ja",
    "ms",
    "nl",
    "pt",
    "ru",
    "zh",
}
ABIS = {"arm64_v8a", "armeabi_v7a", "x86", "x86_64"}


def selected_apk_names(
    names: list[str], primary_abi: str, language: str = "en"
) -> list[str]:
    selected: list[str] = []
    for name in names:
        if not name.lower().endswith(".apk"):
            continue
        stem = PurePosixPath(name).stem.lower()
        final_token = re.split(r"[.]", stem)[-1]
        if final_token in ABIS and final_token != primary_abi:
            continue
        if final_token in LANGUAGES and final_token != language:
            continue
        selected.append(name)
    return sorted(selected, key=lambda name: (PurePosixPath(name).name != "base.apk", name))


def run_adb(serial: str, *args: str) -> str:
    command = ["adb", "-s", serial, *args]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed ({result.returncode}): "
            f"{result.stdout.strip()} {result.stderr.strip()}"
        )
    return result.stdout


def install_archive(serial: str, archive_path: Path, primary_abi: str) -> None:
    with ZipFile(archive_path) as archive, tempfile.TemporaryDirectory(
        prefix="android-bench-app-"
    ) as temp_dir:
        names = selected_apk_names(archive.namelist(), primary_abi)
        if not names:
            raise RuntimeError(f"{archive_path.name} contains no usable APKs")
        extracted: list[str] = []
        for index, name in enumerate(names):
            destination = Path(temp_dir) / f"{index:03d}-{PurePosixPath(name).name}"
            destination.write_bytes(archive.read(name))
            extracted.append(str(destination))
        if len(extracted) == 1:
            run_adb(serial, "install", "-t", "-r", extracted[0])
        else:
            run_adb(serial, "install-multiple", "-t", "-r", *extracted)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: android-bench-install-apps <adb-serial>")
    serial = sys.argv[1]
    run_adb(serial, "wait-for-device")
    abilist = run_adb(serial, "shell", "getprop", "ro.product.cpu.abilist").strip()
    primary_abi = abilist.split(",", 1)[0].replace("-", "_")
    if primary_abi not in ABIS:
        raise RuntimeError(f"unsupported Android primary ABI: {primary_abi!r}")

    for app_path in sorted(APP_DIR.iterdir()):
        suffix = app_path.suffix.lower()
        print(f"Installing {app_path.name}", flush=True)
        if suffix == ".apk":
            run_adb(serial, "install", "-t", "-r", str(app_path))
        elif suffix in {".xapk", ".apkm"}:
            install_archive(serial, app_path, primary_abi)
        app_path.unlink()


if __name__ == "__main__":
    main()
