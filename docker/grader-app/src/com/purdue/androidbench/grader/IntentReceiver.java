package com.purdue.androidbench.grader;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public final class IntentReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        EventRecorder.record("receiver", intent);
    }
}
