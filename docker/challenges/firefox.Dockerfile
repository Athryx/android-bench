FROM android-bench-base:latest
COPY ["apps/org.mozilla.firefox_120.0-2015985722_minAPI21(arm64-v8a)(nodpi)_apkmirror.com.apk", "/challenge/org.mozilla.firefox_120.0-2015985722_minAPI21(arm64-v8a)(nodpi)_apkmirror.com.apk"]
WORKDIR /challenge
