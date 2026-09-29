ARG BASE_IMAGE=kagent_sandbox:latest
FROM ${BASE_IMAGE}

ARG ANDROID_COMMAND_LINE_TOOLS=13114758
ARG ANDROID_PLATFORM=35
ARG ANDROID_BUILD_TOOLS=35.0.0
ARG JADX_VERSION=1.5.3

ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV ANDROID_HOME=/opt/android-sdk
ENV GHIDRA_INSTALL_DIR=/opt/ghidra_11.4_PUBLIC
ENV PATH=/opt/android-sdk/platform-tools:/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/build-tools/${ANDROID_BUILD_TOOLS}:/opt/jadx/bin:${GHIDRA_INSTALL_DIR}/support:/root/.local/bin:${PATH}

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    clang \
    cmake \
    curl \
    default-jdk-headless \
    gdb \
    jq \
    lld \
    llvm \
    netcat-openbsd \
    pkg-config \
    python3 \
    python3-pip \
    python3-venv \
    socat \
    strace \
    unzip \
    wget \
    xz-utils \
    zip \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p ${ANDROID_SDK_ROOT}/cmdline-tools /challenge \
    && wget -q https://dl.google.com/android/repository/commandlinetools-linux-${ANDROID_COMMAND_LINE_TOOLS}_latest.zip -O /tmp/android-tools.zip \
    && unzip -q /tmp/android-tools.zip -d /tmp/android-tools \
    && mv /tmp/android-tools/cmdline-tools ${ANDROID_SDK_ROOT}/cmdline-tools/latest \
    && yes | sdkmanager --licenses >/dev/null \
    && sdkmanager "platform-tools" "platforms;android-${ANDROID_PLATFORM}" "build-tools;${ANDROID_BUILD_TOOLS}" \
    && rm -rf /tmp/android-tools /tmp/android-tools.zip

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

COPY --chmod=0755 docker/install_apps.py /usr/local/bin/android-bench-install-apps

# Ensure pi-mcp-extension is accessible for Pi coding agent in both / and /challenge
RUN for p in /usr/lib/node_modules/pi-mcp-extension /usr/local/lib/node_modules/pi-mcp-extension; do \
        if [ -d "$p" ]; then \
            ln -sf "$p" /pi-mcp-extension \
            && ln -sf "$p" /challenge/pi-mcp-extension; \
        fi; \
    done \
    && chmod 777 /challenge

WORKDIR /challenge
