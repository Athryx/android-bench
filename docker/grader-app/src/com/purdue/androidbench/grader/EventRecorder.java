package com.purdue.androidbench.grader;

import android.content.Intent;
import android.util.Log;
import java.util.Set;
import java.util.TreeSet;

final class EventRecorder {
    private EventRecorder() {}

    static void record(String kind, Intent intent) {
        Set<String> categories = intent.getCategories();
        String category = "";
        if (categories != null && !categories.isEmpty()) {
            category = new TreeSet<>(categories).first();
        }
        String event = safe(kind)
            + "|" + safe(intent.getAction())
            + "|" + safe(intent.getDataString())
            + "|" + safe(category)
            + "|" + safe(intent.getStringExtra("token"));
        Log.i("AndroidBench", event);
    }

    private static String safe(String value) {
        return value == null ? "" : value;
    }
}
