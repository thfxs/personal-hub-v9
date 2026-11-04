package dev.personalhub.v9preview;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.provider.DocumentsContract;
import android.view.View;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.ValueCallback;
import android.widget.Toast;
import androidx.webkit.JavaScriptReplyProxy;
import androidx.webkit.WebMessageCompat;
import androidx.webkit.WebViewAssetLoader;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import org.json.JSONObject;
import java.io.ByteArrayInputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Local-only Android preview. The native bridge is origin- and main-frame-scoped;
 * no addJavascriptInterface, no cleartext LAN exceptions and no arbitrary file paths.
 * File export only proceeds through the Android system document picker.
 */
public final class MainActivity extends Activity {
    private static final String HOST = "appassets.androidplatform.net";
    private static final String ORIGIN = "https://" + HOST;
    private static final String ROOT = "/assets/web/";
    private static final String HOME = ORIGIN + ROOT + "index.html";
    private static final int FILE_IMPORT = 291;
    private static final int FILE_EXPORT = 292;
    private static final int MAX_EXPORT_BYTES = 4 * 1024 * 1024;

    private WebView web;
    private ValueCallback<Uri[]> pendingImport;
    private PendingExport pendingExport;
    private SharedPreferences preferences;
    private final ExecutorService networkExecutor = Executors.newSingleThreadExecutor();
    private volatile PinnedBridgeClient bridgeClient;

    private static class PendingExport {
        final byte[] content;
        final String requestId;
        final JavaScriptReplyProxy reply;
        PendingExport(byte[] content, String requestId, JavaScriptReplyProxy reply) {
            this.content = content;
            this.requestId = requestId;
            this.reply = reply;
        }
    }

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        preferences = getSharedPreferences("personal_hub_native_settings", MODE_PRIVATE);
        try {
            String ip=preferences.getString("bridge_ip", "");
            String fp=preferences.getString("bridge_fingerprint", "");
            int port=preferences.getInt("bridge_port", 0);
            if (!ip.isEmpty() && !fp.isEmpty()) bridgeClient=new PinnedBridgeClient(ip,port,fp,false);
        } catch (IllegalArgumentException ignored) { bridgeClient=null; }
        configureDisplay();
        web = new WebView(this);
        setContentView(web);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setUserAgentString(settings.getUserAgentString() + " PersonalHubV9Shell/1.8");
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(false);
        // A user-selected SAF content:// URI must remain readable by the file chooser.
        settings.setAllowContentAccess(true);
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setGeolocationEnabled(false);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setSafeBrowsingEnabled(true);
        WebView.setWebContentsDebuggingEnabled(false);
        final WebViewAssetLoader loader = new WebViewAssetLoader.Builder()
            .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this)).build();
        web.setWebViewClient(new WebViewClient() {
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri u = request.getUrl();
                if (isAppAsset(u)) {
                    WebResourceResponse local = loader.shouldInterceptRequest(u);
                    return local != null ? local : new WebResourceResponse("text/plain", "UTF-8", new ByteArrayInputStream(new byte[0]));
                }
                // Public GitHub Actions status is the sole allowlisted external read.
                if (isPublicGitHubApi(request)) return null;
                // Block all other web network subresources; user-clicked external links
                // are opened with ACTION_VIEW in shouldOverrideUrlLoading.
                String scheme = u.getScheme();
                if ("https".equals(scheme) || "http".equals(scheme))
                    return new WebResourceResponse("text/plain", "UTF-8", new ByteArrayInputStream(new byte[0]));
                return null;
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri u = request.getUrl();
                if (isAppAsset(u)) return false;
                if (request.isForMainFrame() && ("http".equals(u.getScheme()) || "https".equals(u.getScheme()))) {
                    try { startActivity(new Intent(Intent.ACTION_VIEW, u)); }
                    catch (Exception ex) { Toast.makeText(MainActivity.this, "无法打开外部链接", Toast.LENGTH_SHORT).show(); }
                }
                return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (pendingImport != null) pendingImport.onReceiveValue(null);
                pendingImport = callback;
                try {
                    Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    intent.setType("application/json");
                    intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"application/json", "text/plain", "application/octet-stream"});
                    startActivityForResult(intent, FILE_IMPORT);
                    return true;
                } catch (Exception ex) {
                    pendingImport.onReceiveValue(null);
                    pendingImport = null;
                    Toast.makeText(MainActivity.this, "无法打开系统文件选择器", Toast.LENGTH_SHORT).show();
                    return true;
                }
            }
        });
        setupMessageBridge();
        web.loadUrl(HOME);
    }

    private boolean isAppAsset(Uri u) {
        return u != null && "https".equals(u.getScheme()) && HOST.equals(u.getHost())
            && (u.getPort() == -1 || u.getPort() == 443)
            && u.getPath() != null && u.getPath().startsWith(ROOT);
    }

    private boolean isPublicGitHubApi(WebResourceRequest request) {
        Uri u = request.getUrl();
        String p = u.getPath();
        return "GET".equals(request.getMethod()) && "https".equals(u.getScheme())
            && "api.github.com".equals(u.getHost()) && (u.getPort() == -1 || u.getPort() == 443)
            && p != null && p.matches("/repos/[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}/actions/runs")
            && "per_page=5".equals(u.getEncodedQuery());
    }

    private void setupMessageBridge() {
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            Toast.makeText(this, "系统 WebView 较旧：原生文件导出不可用，请勿录入唯一重要数据", Toast.LENGTH_LONG).show();
            return;
        }
        WebViewCompat.addWebMessageListener(web, "PersonalHubNative", Collections.singleton(ORIGIN),
            (view, message, origin, mainFrame, reply) -> {
                if (!mainFrame || !ORIGIN.equals(origin.toString()) || (view.getUrl() == null || !isAppAsset(Uri.parse(view.getUrl())))) return;
                if (message.getType() != WebMessageCompat.TYPE_STRING) return;
                String requestId = "";
                try {
                    JSONObject obj = new JSONObject(message.getData());
                    String kind = obj.optString("type", "");
                    String id = obj.optString("id", "");
                    requestId = id;
                    if (!id.matches("[A-Za-z0-9_-]{8,64}")) return;
                    if ("save_json".equals(kind)) {
                        handleExport(obj, id, reply);
                    } else if ("device_status".equals(kind)) {
                        reply(reply, id, true, "配置已读取", devicePayload());
                    } else if ("device_preferences".equals(kind)) {
                        if (!obj.has("immersive") || !obj.has("awake") ||
                            !(obj.opt("immersive") instanceof Boolean) || !(obj.opt("awake") instanceof Boolean)) {
                            reply(reply, id, false, "配置值无效", null);return;
                        }
                        preferences.edit().putBoolean("immersive", obj.optBoolean("immersive"))
                            .putBoolean("awake", obj.optBoolean("awake")).apply();
                        configureDisplay();
                        reply(reply, id, true, "设备设置已保存", devicePayload());
                    } else if ("bridge_config".equals(kind) || "bridge_forget".equals(kind) ||
                               "bridge_status".equals(kind) || "bridge_request".equals(kind)) {
                        if (!isBridgePage(view.getUrl())) {
                            reply(reply, id, false, "仅允许本地连接与同步页面访问电脑桥", null);
                            return;
                        }
                        handleBridge(obj,kind,id,reply);
                    } else {
                        reply(reply, id, false, "未知操作", null);
                    }
                } catch (Exception error) {
                    // Reject bad configuration immediately; never expose the raw
                    // request body or a network stacktrace to JavaScript.
                    String errorMessage = error instanceof IllegalArgumentException
                        ? error.getMessage() : "原生请求参数或格式不正确";
                    if (requestId.matches("[A-Za-z0-9_-]{8,64}")) {
                        reply(reply,requestId,false,errorMessage,null);
                    }
                }
            });
    }

    private boolean isBridgePage(String url) {
        if (url == null) return false;
        Uri uri=Uri.parse(url);
        if (!isAppAsset(uri)) return false;
        String path=uri.getPath();
        return (ROOT+"sync/index.html").equals(path) || (ROOT+"remote.html").equals(path);
    }

    private void handleBridge(JSONObject obj,String kind,String id,JavaScriptReplyProxy reply) throws Exception {
        if ("bridge_status".equals(kind)) {
            JSONObject result=new JSONObject();
            PinnedBridgeClient client=bridgeClient;
            result.put("configured",client!=null);
            if (client!=null) {
                result.put("ip",client.getIP());result.put("port",client.getPort());
                result.put("fingerprint",client.getFingerprint());
            }
            result.put("mode","Android HTTPS / certificate SHA-256 pinned");
            reply(reply,id,true,"本机连接配置已读取",result);return;
        }
        if ("bridge_forget".equals(kind)) {
            bridgeClient=null;
            preferences.edit().remove("bridge_ip").remove("bridge_port")
                .remove("bridge_fingerprint").apply();
            reply(reply,id,true,"电脑配置已清除，配对会话已失效",null);return;
        }
        if ("bridge_config".equals(kind)) {
            if (!obj.optBoolean("confirmed",false)) {
                reply(reply,id,false,"请先在电脑本机核对证书指纹并明确确认",null);return;
            }
            String ip=obj.optString("ip", "");
            String fingerprint=obj.optString("fingerprint", "");
            int port=obj.optInt("port",0);
            PinnedBridgeClient client=new PinnedBridgeClient(ip,port,fingerprint,false);
            bridgeClient=client; // A new configuration also discards old pairing cookie.
            preferences.edit().putString("bridge_ip",client.getIP())
                .putInt("bridge_port",client.getPort())
                .putString("bridge_fingerprint",client.getFingerprint()).apply();
            reply(reply,id,true,"电脑证书指纹已固定，请使用临时码配对",null);return;
        }
        if ("bridge_request".equals(kind)) {
            PinnedBridgeClient client=bridgeClient;
            if (client==null) {reply(reply,id,false,"请先核对并保存电脑证书指纹",null);return;}
            String path=obj.optString("path", "");
            String method=obj.optString("method", "GET");
            JSONObject body=obj.optJSONObject("body");
            // Request paths, methods, body limits and HTTPS are independently
            // validated again by PinnedBridgeClient before network I/O.
            networkExecutor.execute(() -> {
                try {
                    PinnedBridgeClient.Response response=client.request(method,path,body==null?"{}":body.toString());
                    JSONObject data=new JSONObject();
                    data.put("status",response.status);
                    data.put("body",new JSONObject(response.json));
                    runOnUiThread(() -> reply(reply,id,true,"电脑已响应",data));
                } catch (Exception exc) {
                    // Never echo raw JSON, passwords or session cookies to JS.
                    String safe=(exc instanceof javax.net.ssl.SSLException ||
                                 exc instanceof java.security.cert.CertificateException)
                        ? "HTTPS 证书验证失败：请在电脑本机重新核对 SHA-256 指纹与 IP"
                        : "电脑桥通信未完成：" + (exc.getMessage()==null?"连接错误":exc.getMessage());
                    if (safe.length()>180)safe=safe.substring(0,180);
                    final String message=safe;
                    runOnUiThread(() -> reply(reply,id,false,message,null));
                }
            });
        }
    }

    private JSONObject devicePayload() throws Exception {
        JSONObject value = new JSONObject();
        value.put("immersive", preferences.getBoolean("immersive", true));
        value.put("awake", preferences.getBoolean("awake", false));
        return value;
    }

    private void configureDisplay() {
        if (preferences == null) return;
        boolean immersive = preferences.getBoolean("immersive", true);
        int flags = View.SYSTEM_UI_FLAG_LAYOUT_STABLE;
        if (immersive) {
            flags |= View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY;
        }
        getWindow().getDecorView().setSystemUiVisibility(flags);
        if (preferences.getBoolean("awake", false)) getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    private void handleExport(JSONObject obj, String id, JavaScriptReplyProxy reply) throws Exception {
        if (pendingExport != null) {reply(reply, id, false, "已有系统保存窗口打开", null);return;}
        String content = obj.optString("content", "");
        if (content.isEmpty()) {reply(reply, id, false, "备份文件为空", null);return;}
        byte[] bytes = content.getBytes(StandardCharsets.UTF_8);
        if (bytes.length > MAX_EXPORT_BYTES) {reply(reply, id, false, "文件超过 4MB 原生导出限制，请先备份到电脑", null);return;}
        new JSONObject(content); // Only JSON backup, never arbitrary file content.
        String name = obj.optString("filename", "personal-hub-backup.json");
        name = name.replaceAll("[^\\p{L}\\p{N}._-]", "_");
        if (name.length() > 100) name = name.substring(0,100);
        if (name.isEmpty() || name.startsWith(".")) name = "personal-hub-backup.json";
        if (!name.endsWith(".json")) name += ".json";
        pendingExport = new PendingExport(bytes, id, reply);
        Intent create = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        create.addCategory(Intent.CATEGORY_OPENABLE);
        create.setType("application/json");
        create.putExtra(Intent.EXTRA_TITLE, name);
        try { startActivityForResult(create, FILE_EXPORT); }
        catch (Exception error) {
            PendingExport pending = pendingExport;pendingExport = null;
            reply(pending.reply, pending.requestId, false, "无法打开系统保存窗口", null);
        }
    }

    private void reply(JavaScriptReplyProxy reply, String id, boolean ok, String message, JSONObject payload) {
        try {
            JSONObject result = new JSONObject();
            result.put("id", id); result.put("ok", ok); result.put("message", message);
            if (payload != null) result.put("data", payload);
            reply.postMessage(result.toString());
        } catch (Exception ignored) { /* Do not log backup content. */ }
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_IMPORT) {
            if (pendingImport != null) {
                pendingImport.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data));
                pendingImport = null;
            }
            return;
        }
        if (requestCode == FILE_EXPORT && pendingExport != null) {
            PendingExport pending = pendingExport;
            pendingExport = null;
            if (resultCode != RESULT_OK || data == null || data.getData() == null) {
                reply(pending.reply, pending.requestId, false, "已取消文件保存，尚未形成外部备份", null);
                return;
            }
            try (OutputStream out = getContentResolver().openOutputStream(data.getData(), "w")) {
                if (out == null) throw new IllegalStateException("没有文件写入权限");
                out.write(pending.content); out.flush();
                reply(pending.reply, pending.requestId, true, "系统文件写入已完成，请在文件管理器核对", null);
            } catch (Exception error) {
                reply(pending.reply, pending.requestId, false, "系统文件写入失败，请勿标记为备份完成", null);
            }
        }
    }

    @Override public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) configureDisplay();
    }
    @Override public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack(); else super.onBackPressed();
    }
    @Override protected void onDestroy() {
        if (pendingImport != null) {pendingImport.onReceiveValue(null);pendingImport = null;}
        if (pendingExport != null) {
            reply(pendingExport.reply, pendingExport.requestId, false, "页面已经关闭，文件保存未确认", null);
            pendingExport = null;
        }
        networkExecutor.shutdownNow();
        if (web != null) {web.destroy();web = null;}
        super.onDestroy();
    }
}
