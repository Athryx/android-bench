FROM android-bench-base:latest
COPY ["apps/OPPO+Store_1.5.3_APKPure.xapk", "/challenge/OPPO+Store_1.5.3_APKPure.xapk"]
WORKDIR /challenge
