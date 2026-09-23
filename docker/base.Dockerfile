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
    clang \
    cmake \
    default-jdk-headless \
    gdb \
    jq \
    lld \
    llvm \
    netcat-openbsd \
    pkg-config \
    python3-venv \
    socat \
    strace \
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

COPY docker/grader-app /tmp/grader-app
RUN bash /tmp/grader-app/build.sh /opt/android-bench/grader.apk \
    && rm -rf /tmp/grader-app

# The remote challenge6 template currently cannot stream the full SHAREit APKM split set. Keep app
# provisioning inside the benchmark sandbox so every fresh VM still receives all 12 target apps.
COPY apps /opt/android-bench/apps
COPY --chmod=0755 docker/install_apps.py /usr/local/bin/android-bench-install-apps
RUN rm -f /opt/android-bench/apps/test_app.apk \
    && chmod -R a+rwX /opt/android-bench/apps

WORKDIR /challenge
