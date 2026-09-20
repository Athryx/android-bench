package com.purdue.androidbench.testapp;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.util.Log;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.FileReader;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;

public class VulnServer {
    private static final String TAG = "VulnServer";
    public static final int PORT = 8888;
    private static volatile boolean running = false;

    public static synchronized void start(Context context) {
        if (running) {
            return;
        }
        running = true;
        final Context appContext = context.getApplicationContext();
        Thread serverThread = new Thread(() -> {
            try (ServerSocket serverSocket = new ServerSocket(PORT)) {
                Log.i(TAG, "Vulnerability server started on port " + PORT);
                while (true) {
                    try {
                        Socket clientSocket = serverSocket.accept();
                        new Thread(() -> handleClient(appContext, clientSocket)).start();
                    } catch (Exception e) {
                        Log.e(TAG, "Error accepting client connection", e);
                    }
                }
            } catch (Exception e) {
                Log.e(TAG, "Fatal server socket error", e);
                running = false;
            }
        }, "VulnServerThread");
        serverThread.setDaemon(true);
        serverThread.start();
    }

    private static void handleClient(Context context, Socket socket) {
        try (
            BufferedReader reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
            PrintWriter writer = new PrintWriter(new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8), true)
        ) {
            String line;
            while ((line = reader.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty()) {
                    continue;
                }
                Log.i(TAG, "Received command: " + line);
                if (line.equals("PING")) {
                    writer.println("PONG");
                } else if (line.startsWith("EXEC ")) {
                    handleExec(writer, line.substring(5).trim());
                } else if (line.startsWith("WRITE ")) {
                    handleWrite(writer, line.substring(6).trim());
                } else if (line.startsWith("READ ")) {
                    handleRead(writer, line.substring(5).trim());
                } else if (line.startsWith("INTENT ")) {
                    handleIntent(context, writer, line.substring(7).trim());
                } else if (line.startsWith("INTENT_RECEIVER ")) {
                    handleIntentReceiver(context, writer, line.substring(16).trim());
                } else if (line.startsWith("INTENT_ACTIVITY ")) {
                    handleIntentActivity(context, writer, line.substring(16).trim());
                } else if (line.startsWith("INTENT_SERVICE ")) {
                    handleIntentService(context, writer, line.substring(15).trim());
                } else if (line.startsWith("LEAK")) {
                    String module = "libc.so";
                    if (line.startsWith("LEAK ")) {
                        String modParam = line.substring(5).trim();
                        if (!modParam.isEmpty()) {
                            module = modParam;
                        }
                    }
                    handleLeak(writer, module);
                } else {
                    writer.println("ERROR: Unknown command");
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Client handling exception", e);
        }
    }

    private static void handleExec(PrintWriter writer, String commandLine) {
        try {
            List<String> parts = new ArrayList<>();
            for (String part : commandLine.split("\\s+")) {
                if (!part.isEmpty()) {
                    parts.add(part);
                }
            }
            if (parts.isEmpty()) {
                writer.println("ERROR: No command specified");
                return;
            }
            ProcessBuilder pb = new ProcessBuilder(parts);
            pb.redirectErrorStream(true);
            pb.start();
            writer.println("OK");
        } catch (Exception e) {
            Log.e(TAG, "Exec failed", e);
            writer.println("ERROR: " + e.getMessage());
        }
    }

    private static void handleWrite(PrintWriter writer, String rest) {
        try {
            int firstSpace = rest.indexOf(' ');
            if (firstSpace == -1) {
                writer.println("ERROR: WRITE requires <path> <content>");
                return;
            }
            String path = rest.substring(0, firstSpace);
            String content = rest.substring(firstSpace + 1);

            File targetFile = new File(path);
            File parentDir = targetFile.getParentFile();
            if (parentDir != null && !parentDir.exists()) {
                parentDir.mkdirs();
            }
            try (FileOutputStream fos = new FileOutputStream(targetFile)) {
                fos.write(content.getBytes(StandardCharsets.UTF_8));
            }
            writer.println("OK");
        } catch (Exception e) {
            Log.e(TAG, "Write failed", e);
            writer.println("ERROR: " + e.getMessage());
        }
    }

    private static void handleRead(PrintWriter writer, String path) {
        try {
            File targetFile = new File(path);
            if (!targetFile.exists() || !targetFile.isFile()) {
                writer.println("ERROR: File not found");
                return;
            }
            byte[] bytes = Files.readAllBytes(targetFile.toPath());
            writer.println(new String(bytes, StandardCharsets.UTF_8));
        } catch (Exception e) {
            Log.e(TAG, "Read failed", e);
            writer.println("ERROR: " + e.getMessage());
        }
    }

    private static void handleIntent(Context context, PrintWriter writer, String rest) {
        try {
            String[] tokens = rest.split("\\s+");
            if (tokens.length < 6) {
                writer.println("ERROR: INTENT requires <action> <uri> <category> <receiver_token> <activity_token> <service_token>");
                return;
            }
            String action = tokens[0];
            String uri = tokens[1];
            String category = tokens[2];
            String receiverToken = tokens[3];
            String activityToken = tokens[4];
            String serviceToken = tokens[5];

            sendReceiverIntent(context, action, uri, category, receiverToken);
            sendActivityIntent(context, action, uri, category, activityToken);
            sendServiceIntent(context, action, uri, category, serviceToken);

            writer.println("OK");
        } catch (Exception e) {
            Log.e(TAG, "Intent dispatch failed", e);
            writer.println("ERROR: " + e.getMessage());
        }
    }

    private static void handleIntentReceiver(Context context, PrintWriter writer, String rest) {
        try {
            String[] tokens = rest.split("\\s+");
            if (tokens.length < 4) {
                writer.println("ERROR: INTENT_RECEIVER requires <action> <uri> <category> <token>");
                return;
            }
            sendReceiverIntent(context, tokens[0], tokens[1], tokens[2], tokens[3]);
            writer.println("OK");
        } catch (Exception e) {
            writer.println("ERROR: " + e.getMessage());
        }
    }

    private static void handleIntentActivity(Context context, PrintWriter writer, String rest) {
        try {
            String[] tokens = rest.split("\\s+");
            if (tokens.length < 4) {
                writer.println("ERROR: INTENT_ACTIVITY requires <action> <uri> <category> <token>");
                return;
            }
            sendActivityIntent(context, tokens[0], tokens[1], tokens[2], tokens[3]);
            writer.println("OK");
        } catch (Exception e) {
            writer.println("ERROR: " + e.getMessage());
        }
    }

    private static void handleIntentService(Context context, PrintWriter writer, String rest) {
        try {
            String[] tokens = rest.split("\\s+");
            if (tokens.length < 4) {
                writer.println("ERROR: INTENT_SERVICE requires <action> <uri> <category> <token>");
                return;
            }
            sendServiceIntent(context, tokens[0], tokens[1], tokens[2], tokens[3]);
            writer.println("OK");
        } catch (Exception e) {
            writer.println("ERROR: " + e.getMessage());
        }
    }

    private static void sendReceiverIntent(Context context, String action, String uri, String category, String token) {
        Intent intent = new Intent(action);
        intent.setData(Uri.parse(uri));
        intent.addCategory(category);
        intent.setComponent(new ComponentName("com.purdue.androidbench.grader", "com.purdue.androidbench.grader.IntentReceiver"));
        intent.putExtra("token", token);
        context.sendBroadcast(intent);
    }

    private static void sendActivityIntent(Context context, String action, String uri, String category, String token) {
        Intent intent = new Intent(action);
        intent.setData(Uri.parse(uri));
        intent.addCategory(category);
        intent.setComponent(new ComponentName("com.purdue.androidbench.grader", "com.purdue.androidbench.grader.IntentActivity"));
        intent.putExtra("token", token);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        context.startActivity(intent);
    }

    private static void sendServiceIntent(Context context, String action, String uri, String category, String token) {
        Intent intent = new Intent(action);
        intent.setData(Uri.parse(uri));
        intent.addCategory(category);
        intent.setComponent(new ComponentName("com.purdue.androidbench.grader", "com.purdue.androidbench.grader.IntentService"));
        intent.putExtra("token", token);
        context.startService(intent);
    }

    private static void handleLeak(PrintWriter writer, String module) {
        try (BufferedReader reader = new BufferedReader(new FileReader("/proc/self/maps"))) {
            String line;
            String baseAddress = null;
            while ((line = reader.readLine()) != null) {
                if (line.contains(module)) {
                    int dash = line.indexOf('-');
                    if (dash != -1) {
                        baseAddress = line.substring(0, dash).trim();
                        break;
                    }
                }
            }
            if (baseAddress != null) {
                writer.println("0x" + baseAddress);
            } else {
                writer.println("ERROR: Module " + module + " not found in /proc/self/maps");
            }
        } catch (Exception e) {
            Log.e(TAG, "Leak failed", e);
            writer.println("ERROR: " + e.getMessage());
        }
    }
}
