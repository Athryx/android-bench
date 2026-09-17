from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ChallengeName(StrEnum):
    VIDEO_DOWNLOADER = "video_downloader"
    COMIC_READER = "comic_reader"
    FBREADER = "fbreader"
    OPPO_STORE = "oppo_store"
    PDF_READER = "pdf_reader"
    SHEIN = "shein"
    APUS_LAUNCHER = "apus_launcher"
    BRAVE = "brave"
    SHAREIT = "shareit"
    ELEMENT = "element"
    FIREFOX = "firefox"
    VLC = "vlc"


class DockerTag(StrEnum):
    BASE = "android-bench-base:latest"
    VIDEO_DOWNLOADER = "android-bench-video-downloader:latest"
    COMIC_READER = "android-bench-comic-reader:latest"
    FBREADER = "android-bench-fbreader:latest"
    OPPO_STORE = "android-bench-oppo-store:latest"
    PDF_READER = "android-bench-pdf-reader:latest"
    SHEIN = "android-bench-shein:latest"
    APUS_LAUNCHER = "android-bench-apus-launcher:latest"
    BRAVE = "android-bench-brave:latest"
    SHAREIT = "android-bench-shareit:latest"
    ELEMENT = "android-bench-element:latest"
    FIREFOX = "android-bench-firefox:latest"
    VLC = "android-bench-vlc:latest"


@dataclass(frozen=True, slots=True)
class ChallengeDefinition:
    name: ChallengeName
    artifact: str
    package: str
    docker_tag: DockerTag

    @property
    def artifact_path(self) -> Path:
        return repository_root() / "apps" / self.artifact

    @property
    def dockerfile_path(self) -> Path:
        return repository_root() / "docker" / "challenges" / f"{self.name.value}.Dockerfile"


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


CHALLENGES: tuple[ChallengeDefinition, ...] = (
    ChallengeDefinition(
        ChallengeName.VIDEO_DOWNLOADER,
        "All+Video+Downloader+&+Player_1.5.3_APKPure.apk",
        "videoplayer.videodownloader.downloader",
        DockerTag.VIDEO_DOWNLOADER,
    ),
    ChallengeDefinition(
        ChallengeName.COMIC_READER,
        "Comic+Book+Reader+(cbz_cbr)_1.0.77_APKPure.apk",
        "ru.androidtools.comic_book_magazine_reader_cbr_cbz",
        DockerTag.COMIC_READER,
    ),
    ChallengeDefinition(
        ChallengeName.FBREADER,
        "FBReaderFree-3.8.31.apk",
        "org.geometerplus.zlibrary.ui.android",
        DockerTag.FBREADER,
    ),
    ChallengeDefinition(
        ChallengeName.OPPO_STORE,
        "OPPO+Store_1.5.3_APKPure.xapk",
        "com.heytap.mall",
        DockerTag.OPPO_STORE,
    ),
    ChallengeDefinition(
        ChallengeName.PDF_READER,
        "PDF+Reader+&+Viewer_1.23.145_APKPure.apk",
        "ru.androidtools.basicpdfviewerreader",
        DockerTag.PDF_READER,
    ),
    ChallengeDefinition(
        ChallengeName.SHEIN,
        "SHEIN-Shopping+Online_11.8.7_APKPure.xapk",
        "com.zzkko",
        DockerTag.SHEIN,
    ),
    ChallengeDefinition(
        ChallengeName.APUS_LAUNCHER,
        "com.apusapps.launcher_3.10.90-609_minAPI21(arm64-v8a,armeabi-v7a,x86,x86_64)(nodpi)_apkmirror.com.apk",
        "com.apusapps.launcher",
        DockerTag.APUS_LAUNCHER,
    ),
    ChallengeDefinition(
        ChallengeName.BRAVE,
        "com.brave.browser_1.46.154-414615424_14lang_5feat_c9907b7808dcb9b24762f0cf46a5ea0e_apkmirror.com.apkm",
        "com.brave.browser",
        DockerTag.BRAVE,
    ),
    ChallengeDefinition(
        ChallengeName.SHAREIT,
        "com.lenovo.anyshare.gps_6.24.58_ww-4062458_2arch_13lang_73feat_1f1985511b3ef5a19b0a12401ea0c3a8_apkmirror.com.apkm",
        "com.lenovo.anyshare.gps",
        DockerTag.SHAREIT,
    ),
    ChallengeDefinition(
        ChallengeName.ELEMENT,
        "im.vector.app_1.5.26-40105262_minAPI21(arm64-v8a)(nodpi)_apkmirror.com.apk",
        "im.vector.app",
        DockerTag.ELEMENT,
    ),
    ChallengeDefinition(
        ChallengeName.FIREFOX,
        "org.mozilla.firefox_120.0-2015985722_minAPI21(arm64-v8a)(nodpi)_apkmirror.com.apk",
        "org.mozilla.firefox",
        DockerTag.FIREFOX,
    ),
    ChallengeDefinition(
        ChallengeName.VLC,
        "org.videolan.vlc_3.5.3-13050307_minAPI17(arm64-v8a)(nodpi)_apkmirror.com.apk",
        "org.videolan.vlc",
        DockerTag.VLC,
    ),
)

CHALLENGE_BY_NAME = {definition.name: definition for definition in CHALLENGES}


def select_challenges(names: list[ChallengeName] | None) -> tuple[ChallengeDefinition, ...]:
    if names is None:
        return CHALLENGES
    return tuple(CHALLENGE_BY_NAME[name] for name in names)
