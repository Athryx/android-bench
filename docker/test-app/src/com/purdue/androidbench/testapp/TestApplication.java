package com.purdue.androidbench.testapp;

import android.app.Application;
import android.util.Log;

public class TestApplication extends Application {
    private static final String TAG = "TestApplication";

    @Override
    public void onCreate() {
        super.onCreate();
        Log.i(TAG, "TestApplication initializing VulnServer");
        VulnServer.start(this);
    }
}
