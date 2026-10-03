package com.builder.generated;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;

public class MainActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);

        WebView web = new WebView(this);
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);

        web.setWebViewClient(new WebViewClient());

        String url = readConfig();
        if (url != null && !url.isEmpty()) {
            web.loadUrl(url);
        } else {
            web.loadUrl("file:///android_asset/www/index.html");
        }
    }

    private String readConfig() {
        try {
            InputStream in = getAssets().open("start_url.txt");
            BufferedReader r = new BufferedReader(new InputStreamReader(in));
            String value = r.readLine();
            r.close();
            return value == null ? "" : value.trim();
        } catch (Exception e) {
            return "";
        }
    }
}
