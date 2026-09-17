FROM android-bench-base:latest
COPY ["apps/com.apusapps.launcher_3.10.90-609_minAPI21(arm64-v8a,armeabi-v7a,x86,x86_64)(nodpi)_apkmirror.com.apk", "/challenge/com.apusapps.launcher_3.10.90-609_minAPI21(arm64-v8a,armeabi-v7a,x86,x86_64)(nodpi)_apkmirror.com.apk"]
WORKDIR /challenge
