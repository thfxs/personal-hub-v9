#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Portable Java source compilation smoke gate for Android MainActivity.

This generates minimal Android/AndroidX *compile-only stubs* and compiles both
real application Java files with javac. Stubs are not shipped with the APK and
this never claims to replace Gradle/Android SDK or check AndroidX binaries.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_SRC = Path(os.environ.get('PH_ANDROID_SOURCE_DIR', str(ROOT / 'android/app/src/main/java/dev/personalhub/v9preview')))
STUBS = {
'android/content/Context.java': '''package android.content;
public class Context {
 public static final int MODE_PRIVATE=0;
 public SharedPreferences getSharedPreferences(String name,int mode){return null;}
 public ContentResolver getContentResolver(){return null;}
}''',
'android/content/SharedPreferences.java': '''package android.content;
public interface SharedPreferences {
 String getString(String key,String def); int getInt(String key,int def);
 boolean getBoolean(String key,boolean def); Editor edit();
 interface Editor {Editor putString(String key,String value);Editor putInt(String key,int value);
 Editor putBoolean(String key,boolean value);Editor remove(String key);void apply();}
}''',
'android/content/ContentResolver.java': '''package android.content;
import android.net.Uri;import java.io.OutputStream;import java.io.FileNotFoundException;
public abstract class ContentResolver {public abstract OutputStream openOutputStream(Uri uri,String mode) throws FileNotFoundException;}
''',
'android/content/Intent.java': '''package android.content;
import android.net.Uri;
public class Intent {
 public static final String ACTION_VIEW="view", ACTION_OPEN_DOCUMENT="open",ACTION_CREATE_DOCUMENT="create";
 public static final String CATEGORY_OPENABLE="openable",EXTRA_MIME_TYPES="types",EXTRA_TITLE="title";
 public Intent(){} public Intent(String name){} public Intent(String name,Uri uri){}
 public Intent addCategory(String s){return this;}public Intent setType(String s){return this;}
 public Intent putExtra(String key,String value){return this;}
 public Intent putExtra(String key,String[] value){return this;}
 public Uri getData(){return null;}
}''',
'android/net/Uri.java': '''package android.net;
public abstract class Uri {
 public static Uri parse(String url){return null;}
 public abstract String getScheme(); public abstract String getHost();public abstract int getPort();
 public abstract String getPath();public abstract String getEncodedQuery();
}''',
'android/os/Bundle.java': 'package android.os;public class Bundle {}',
'android/view/View.java': '''package android.view;
public class View {
 public static final int SYSTEM_UI_FLAG_LAYOUT_STABLE=1,SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN=2,
 SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION=4,SYSTEM_UI_FLAG_FULLSCREEN=8,
 SYSTEM_UI_FLAG_HIDE_NAVIGATION=16,SYSTEM_UI_FLAG_IMMERSIVE_STICKY=32;
 public void setSystemUiVisibility(int n){}
}''',
'android/view/WindowManager.java': '''package android.view;
public interface WindowManager {class LayoutParams {public static final int FLAG_KEEP_SCREEN_ON=128;}}
''',
'android/view/Window.java': '''package android.view;
public class Window {public View getDecorView(){return null;}public void addFlags(int n){}public void clearFlags(int n){}}
''',
'android/app/Activity.java': '''package android.app;
import android.content.Context;import android.content.Intent;import android.net.Uri;
import android.os.Bundle;import android.view.View;import android.view.Window;
public class Activity extends Context {
 public static final int RESULT_OK=-1;
 public void onCreate(Bundle b){}protected void onActivityResult(int request,int result,Intent data){}
 public void onWindowFocusChanged(boolean focus){}public void onBackPressed(){}
 protected void onDestroy(){}
 public Window getWindow(){return null;}public void setContentView(View v){}
 public void startActivityForResult(Intent i,int n){}public void startActivity(Intent i){}
 public void runOnUiThread(Runnable work){}
}''',
'android/webkit/ValueCallback.java': '''package android.webkit;
public interface ValueCallback<T>{void onReceiveValue(T value);}
''',
'android/webkit/WebView.java': '''package android.webkit;
import android.content.Context;import android.view.View;
public class WebView extends View {
 public WebView(Context c){}public WebSettings getSettings(){return null;}
 public static void setWebContentsDebuggingEnabled(boolean v){}
 public void setWebViewClient(WebViewClient c){}public void setWebChromeClient(WebChromeClient c){}
 public void loadUrl(String s){}public String getUrl(){return null;}
 public boolean canGoBack(){return false;}public void goBack(){}public void destroy(){}
}''',
'android/webkit/WebSettings.java': '''package android.webkit;
public class WebSettings {
 public static final int MIXED_CONTENT_NEVER_ALLOW=1;
 public void setJavaScriptEnabled(boolean v){}public String getUserAgentString(){return "";}
 public void setUserAgentString(String s){}public void setDomStorageEnabled(boolean v){}
 public void setDatabaseEnabled(boolean v){}public void setAllowFileAccess(boolean v){}
 public void setAllowContentAccess(boolean v){}public void setAllowFileAccessFromFileURLs(boolean v){}
 public void setAllowUniversalAccessFromFileURLs(boolean v){}
 public void setMixedContentMode(int v){}public void setJavaScriptCanOpenWindowsAutomatically(boolean v){}
 public void setSupportMultipleWindows(boolean v){}public void setGeolocationEnabled(boolean v){}
 public void setMediaPlaybackRequiresUserGesture(boolean v){}public void setSafeBrowsingEnabled(boolean v){}
}''',
'android/webkit/WebResourceRequest.java': '''package android.webkit;
import android.net.Uri;public interface WebResourceRequest {
 Uri getUrl();String getMethod();boolean isForMainFrame();
}''',
'android/webkit/WebResourceResponse.java': '''package android.webkit;
import java.io.InputStream;public class WebResourceResponse {
 public WebResourceResponse(String mime,String encoding,InputStream data){}
}''',
'android/webkit/WebViewClient.java': '''package android.webkit;
public class WebViewClient {
 public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request){return null;}
 public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){return false;}
}''',
'android/webkit/WebChromeClient.java': '''package android.webkit;
import android.net.Uri;import android.content.Intent;
public class WebChromeClient {
 public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> cb,FileChooserParams params){return false;}
 public static class FileChooserParams {public static Uri[] parseResult(int resultCode,Intent data){return null;}}
}''',
'android/widget/Toast.java': '''package android.widget;
import android.content.Context;
public class Toast {
 public static final int LENGTH_SHORT=0,LENGTH_LONG=1;
 public static Toast makeText(Context c,String message,int duration){return null;}
 public void show(){}
}''',
'android/provider/DocumentsContract.java': 'package android.provider;public class DocumentsContract {}',
'androidx/webkit/JavaScriptReplyProxy.java': '''package androidx.webkit;
public abstract class JavaScriptReplyProxy {public abstract void postMessage(String s);}
''',
'androidx/webkit/WebMessageCompat.java': '''package androidx.webkit;
public class WebMessageCompat {
 public static final int TYPE_STRING=0;public int getType(){return 0;}public String getData(){return null;}
}''',
'androidx/webkit/WebViewFeature.java': '''package androidx.webkit;
public class WebViewFeature {
 public static final String WEB_MESSAGE_LISTENER="listener";
 public static boolean isFeatureSupported(String f){return false;}
}''',
'androidx/webkit/WebViewCompat.java': '''package androidx.webkit;
import android.webkit.WebView;import android.net.Uri;import java.util.Set;
public class WebViewCompat {
 public interface WebMessageListener {
  void onPostMessage(WebView view,WebMessageCompat message,Uri origin,boolean isMainFrame,JavaScriptReplyProxy reply);
 }
 public static void addWebMessageListener(WebView view,String name,Set<String> origins,WebMessageListener listener){}
}''',
'androidx/webkit/WebViewAssetLoader.java': '''package androidx.webkit;
import android.content.Context;import android.net.Uri;import android.webkit.WebResourceResponse;
public class WebViewAssetLoader {
 public interface PathHandler {}
 public static class AssetsPathHandler implements PathHandler{public AssetsPathHandler(Context ctx){}}
 public static class Builder {
  public Builder addPathHandler(String path,PathHandler handler){return this;}
  public WebViewAssetLoader build(){return new WebViewAssetLoader();}
 }
 public WebResourceResponse shouldInterceptRequest(Uri uri){return null;}
}''',
'org/json/JSONObject.java': '''package org.json;
public class JSONObject {
 public JSONObject(){}public JSONObject(String value){}
 public String optString(String key,String def){return def;}
 public boolean has(String key){return false;}public Object opt(String key){return null;}
 public boolean optBoolean(String key,boolean def){return def;} public boolean optBoolean(String key){return false;}
 public int optInt(String key,int def){return def;}
 public JSONObject optJSONObject(String key){return null;}
 public JSONObject put(String key,Object value){return this;}
 public String toString(){return "{}";}
}''',
}

def main():
    if not shutil.which('javac'):
        raise RuntimeError('javac unavailable: gate MUST fail instead of silently skip')
    with tempfile.TemporaryDirectory(prefix='personalhub-android-stubs-') as d:
        d=Path(d)
        for name,source in STUBS.items():
            f=d/'stubs'/name
            f.parent.mkdir(parents=True,exist_ok=True)
            f.write_text(source,encoding='utf-8')
        originals=[APP_SRC/'MainActivity.java',APP_SRC/'PinnedBridgeClient.java']
        if any(not f.exists() for f in originals):
            raise RuntimeError('Android application source missing')
        sources=[str(f) for f in (d/'stubs').rglob('*.java')]+list(map(str,originals))
        p=subprocess.run(['javac','--release','17','-encoding','UTF-8','-Xlint:unchecked',
                         '-d',str(d/'classes')]+sources,
                         capture_output=True,text=True,timeout=35)
        if p.returncode:
            print(p.stdout,p.stderr)
            raise RuntimeError('MainActivity or PinnedBridgeClient failed to compile against compile-only API surface')
        print('[PASS] Both real Android Java sources compiled with JDK 17 against documented, minimal API stubs')
        print('[NOT VERIFIED] Android SDK/AndroidX binaries, resource linking, dex, real APK, HarmonyOS 2.0')

if __name__=='__main__':main()
