#!/usr/bin/env bash
set -euo pipefail

app_dir=$(cd "$(dirname "$0")" && pwd)
output=${1:-${app_dir}/../../challenges/apps/test_app.apk}
build_dir=$(mktemp -d -t android-bench-test-app.XXXXXX)
trap 'rm -rf "${build_dir}"' EXIT
android_jar=${ANDROID_SDK_ROOT}/platforms/android-35/android.jar
build_tools=${ANDROID_SDK_ROOT}/build-tools/35.0.0

mkdir -p "${build_dir}/classes" "${build_dir}/dex" "$(dirname "${output}")"

"${build_tools}/aapt2" link \
    --manifest "${app_dir}/AndroidManifest.xml" \
    -I "${android_jar}" \
    --min-sdk-version 26 \
    --target-sdk-version 35 \
    -o "${build_dir}/unsigned.apk"

mapfile -t java_sources < <(find "${app_dir}/src" -name '*.java' -print)
javac -source 17 -target 17 -classpath "${android_jar}" \
    -d "${build_dir}/classes" "${java_sources[@]}"

mapfile -t class_files < <(find "${build_dir}/classes" -name '*.class' -print)
"${build_tools}/d8" --min-api 26 --lib "${android_jar}" \
    --output "${build_dir}/dex" "${class_files[@]}"
zip -q -j "${build_dir}/unsigned.apk" "${build_dir}/dex/classes.dex"

keytool -genkeypair -noprompt \
    -keystore "${build_dir}/testapp.keystore" \
    -storepass android \
    -keypass android \
    -alias testapp \
    -keyalg RSA \
    -keysize 2048 \
    -validity 10000 \
    -dname "CN=Android Bench Test App"
"${build_tools}/zipalign" -f 4 \
    "${build_dir}/unsigned.apk" "${build_dir}/aligned.apk"
"${build_tools}/apksigner" sign \
    --ks "${build_dir}/testapp.keystore" \
    --ks-pass pass:android \
    --key-pass pass:android \
    --out "${output}" \
    "${build_dir}/aligned.apk"
