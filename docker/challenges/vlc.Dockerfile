FROM android-bench-base:latest
COPY ["apps/org.videolan.vlc_3.5.3-13050307_minAPI17(arm64-v8a)(nodpi)_apkmirror.com.apk", "/challenge/org.videolan.vlc_3.5.3-13050307_minAPI17(arm64-v8a)(nodpi)_apkmirror.com.apk"]
WORKDIR /challenge
