FROM android-bench-base:latest
COPY ["apps/com.brave.browser_1.46.154-414615424_14lang_5feat_c9907b7808dcb9b24762f0cf46a5ea0e_apkmirror.com.apkm", "/challenge/com.brave.browser_1.46.154-414615424_14lang_5feat_c9907b7808dcb9b24762f0cf46a5ea0e_apkmirror.com.apkm"]
WORKDIR /challenge
