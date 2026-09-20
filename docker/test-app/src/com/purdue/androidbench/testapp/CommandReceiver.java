package com.purdue.androidbench.testapp;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

public class CommandReceiver extends BroadcastReceiver {
    private static final String TAG = "CommandReceiver";

    @Override
    public void onReceive(Context context, Intent intent) {
        Log.i(TAG, "CommandReceiver received intent: " + intent.getAction());
        VulnServer.start(context);
    }
}
