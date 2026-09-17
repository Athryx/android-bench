FROM android-bench-base:latest
COPY ["apps/FBReaderFree-3.8.31.apk", "/challenge/FBReaderFree-3.8.31.apk"]
WORKDIR /challenge
