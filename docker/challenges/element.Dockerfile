FROM android-bench-base:latest
COPY ["apps/im.vector.app_1.5.26-40105262_minAPI21(arm64-v8a)(nodpi)_apkmirror.com.apk", "/challenge/im.vector.app_1.5.26-40105262_minAPI21(arm64-v8a)(nodpi)_apkmirror.com.apk"]
WORKDIR /challenge
