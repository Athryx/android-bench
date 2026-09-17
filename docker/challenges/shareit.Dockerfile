FROM android-bench-base:latest
COPY ["apps/com.lenovo.anyshare.gps_6.24.58_ww-4062458_2arch_13lang_73feat_1f1985511b3ef5a19b0a12401ea0c3a8_apkmirror.com.apkm", "/challenge/com.lenovo.anyshare.gps_6.24.58_ww-4062458_2arch_13lang_73feat_1f1985511b3ef5a19b0a12401ea0c3a8_apkmirror.com.apkm"]
WORKDIR /challenge
