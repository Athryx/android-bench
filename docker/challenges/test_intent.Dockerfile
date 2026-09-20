FROM android-bench-base:latest
COPY ["apps/test_app.apk", "/challenge/test_app.apk"]
WORKDIR /challenge
