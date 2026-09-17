FROM ubuntu:24.04

ARG CODEX_CLI_VERSION=0.144.4
ARG ANDROID_COMMAND_LINE_TOOLS=13114758
ARG ANDROID_PLATFORM=35
ARG ANDROID_BUILD_TOOLS=35.0.0
ARG NDK_VERSION=r26b
ARG JADX_VERSION=1.5.3

ENV DEBIAN_FRONTEND=noninteractive
ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_NDK_HOME=/opt/android-ndk-r26b
ENV GHIDRA_INSTALL_DIR=/opt/ghidra_11.4_PUBLIC
ENV PATH=/opt/android-sdk/platform-tools:/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/build-tools/35.0.0:/opt/android-ndk-r26b:/opt/jadx/bin:/opt/ghidra_11.4_PUBLIC/support:/root/.local/bin:/opt/codex-cli/codex_cli_bin/bin:${PATH}

RUN apt-get update && apt-get install -y --no-install-recommends \
    aapt \
    android-sdk-platform-tools \
    apktool \
    binutils \
    build-essential \
    ca-certificates \
    clang \
    cmake \
    curl \
    default-jdk-headless \
    fd-find \
    file \
    gdb \
    git \
    jq \
    lld \
    llvm \
    make \
    netcat-openbsd \
    p7zip-full \
    pkg-config \
    python3 \
    python3-pip \
    python3-venv \
    ripgrep \
    socat \
    strace \
    unzip \
    wget \
    xz-utils \
    zip \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p ${ANDROID_SDK_ROOT}/cmdline-tools /data /challenge \
    && wget -q https://dl.google.com/android/repository/commandlinetools-linux-${ANDROID_COMMAND_LINE_TOOLS}_latest.zip -O /tmp/android-tools.zip \
    && unzip -q /tmp/android-tools.zip -d /tmp/android-tools \
    && mv /tmp/android-tools/cmdline-tools ${ANDROID_SDK_ROOT}/cmdline-tools/latest \
    && yes | sdkmanager --licenses >/dev/null \
    && sdkmanager "platform-tools" "platforms;android-${ANDROID_PLATFORM}" "build-tools;${ANDROID_BUILD_TOOLS}" \
    && rm -rf /tmp/android-tools /tmp/android-tools.zip

RUN wget -q https://dl.google.com/android/repository/android-ndk-${NDK_VERSION}-linux.zip -O /tmp/ndk.zip \
    && unzip -q /tmp/ndk.zip -d /opt \
    && rm /tmp/ndk.zip

RUN wget -q https://github.com/skylot/jadx/releases/download/v${JADX_VERSION}/jadx-${JADX_VERSION}.zip -O /tmp/jadx.zip \
    && mkdir -p /opt/jadx \
    && unzip -q /tmp/jadx.zip -d /opt/jadx \
    && rm /tmp/jadx.zip

RUN wget -q https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_11.4_build/ghidra_11.4_PUBLIC_20250620.zip -O /tmp/ghidra.zip \
    && unzip -q /tmp/ghidra.zip -d /opt \
    && rm /tmp/ghidra.zip

RUN python3 -m pip install --break-system-packages --no-cache-dir \
    frida-tools \
    uv \
    && uv tool install git+https://github.com/cellebrite-labs/ghidra-rpc

RUN python3 -m pip install --no-cache-dir --target /opt/codex-cli \
    "openai-codex-cli-bin==${CODEX_CLI_VERSION}" \
    && test -x /opt/codex-cli/codex_cli_bin/bin/codex

RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @earendil-works/pi-coding-agent pi-mcp-extension \
    && rm -rf /var/lib/apt/lists/* /root/.npm

RUN curl -fsSL https://claude.ai/install.sh | bash \
    && test -x /root/.local/bin/claude \
    && cp /root/.local/bin/claude /usr/local/bin/claude \
    && chmod 0755 /usr/local/bin/claude

COPY docker/grader-app /tmp/grader-app
RUN bash /tmp/grader-app/build.sh /opt/android-bench/grader.apk \
    && rm -rf /tmp/grader-app

# The remote challenge6 template currently cannot stream the full SHAREit APKM split set. Keep app
# provisioning inside the benchmark sandbox so every fresh VM still receives all 12 target apps.
COPY apps /opt/android-bench/apps
COPY --chmod=0755 docker/install_apps.py /usr/local/bin/android-bench-install-apps
RUN chmod -R a+rwX /opt/android-bench/apps

WORKDIR /challenge
