package com.purdue.androidbench.grader;

import android.app.Activity;
import android.os.Bundle;

public final class IntentActivity extends Activity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        EventRecorder.record("activity", getIntent());
        finish();
    }
}
