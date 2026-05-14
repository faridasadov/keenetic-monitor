package az.keenetic.monitor;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.http.SslError;
import android.os.Bundle;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.content.Context;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

public class MainActivity extends Activity {
    private static final String PREFS = "keenetic_monitor";
    private static final String KEY_URL = "dashboard_url";

    private WebView webView;
    private SharedPreferences preferences;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        preferences = getSharedPreferences(PREFS, MODE_PRIVATE);

        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(245, 247, 250));
        webView.setSystemUiVisibility(View.SYSTEM_UI_FLAG_LAYOUT_STABLE);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);

        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new DashboardWebViewClient());

        FrameLayout root = new FrameLayout(this);
        root.addView(webView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
        ));
        setContentView(root);

        if (savedInstanceState == null) {
            String url = dashboardUrl();
            if (BuildConfig.DASHBOARD_URL.equals(url)) {
                showUrlDialog(url);
            } else {
                webView.loadUrl(url);
            }
        } else {
            webView.restoreState(savedInstanceState);
        }
    }

    private String dashboardUrl() {
        return preferences.getString(KEY_URL, BuildConfig.DASHBOARD_URL);
    }

    private String normalizeUrl(String value) {
        String trimmed = value == null ? "" : value.trim();
        if (trimmed.isEmpty()) return BuildConfig.DASHBOARD_URL;
        if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
            return "http://" + trimmed;
        }
        return trimmed;
    }

    private void saveAndLoadUrl(String value) {
        String url = normalizeUrl(value);
        preferences.edit().putString(KEY_URL, url).apply();
        webView.loadUrl(url);
    }

    private void showUrlDialog(String currentUrl) {
        final EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setText(currentUrl);
        input.setSelection(input.getText().length());
        input.setHint("http://SERVER-IP:8000");

        int padding = dp(20);
        LinearLayout container = new LinearLayout(this);
        container.setPadding(padding, 8, padding, 0);
        container.addView(input, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        ));

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle("Keenetic Monitor ünvanı")
                .setMessage("Telefonun açdığı server ünvanını yaz. Məsələn: http://192.168.1.10:8000")
                .setView(container)
                .setPositiveButton("Aç", null)
                .setNegativeButton("Default", null)
                .create();
        dialog.setOnShowListener((d) -> {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener((v) -> {
                saveAndLoadUrl(input.getText().toString());
                hideKeyboard(input);
                dialog.dismiss();
            });
            dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setOnClickListener((v) -> {
                saveAndLoadUrl(BuildConfig.DASHBOARD_URL);
                hideKeyboard(input);
                dialog.dismiss();
            });
            input.requestFocus();
        });
        dialog.show();
    }

    private void showErrorPage(String failingUrl, String message) {
        String safeUrl = escape(failingUrl);
        String safeMessage = escape(message);
        String html = "<!doctype html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'>"
                + "<style>body{margin:0;font-family:sans-serif;background:#f5f7fa;color:#172033}"
                + ".box{padding:24px}.card{background:#fff;border:1px solid #dce3ed;border-radius:10px;padding:18px;box-shadow:0 12px 34px rgba(16,24,40,.10)}"
                + "h1{font-size:22px;margin:0 0 8px}p{color:#697386;line-height:1.45}code{display:block;white-space:normal;overflow-wrap:anywhere;background:#f9fbfd;border:1px solid #dce3ed;border-radius:8px;padding:10px}"
                + ".hint{margin-top:14px;color:#b45309;font-weight:700}</style></head><body><div class='box'><div class='card'>"
                + "<h1>Dashboard açılmadı</h1>"
                + "<p>Telefon bu ünvana çata bilmir:</p><code>" + safeUrl + "</code>"
                + "<p class='hint'>" + safeMessage + "</p>"
                + "<p>Server IP-ni düzgün yaz: məsələn <b>http://192.168.1.10:8000</b>. Telefon və server eyni şəbəkədə olmalıdır.</p>"
                + "<p>Tətbiqdə geri düyməsini basıb yenidən ünvan daxil edə bilərsən.</p>"
                + "</div></div></body></html>";
        webView.loadDataWithBaseURL(null, html, "text/html", "UTF-8", null);
    }

    private String escape(String value) {
        if (value == null) return "";
        return value
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;");
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void hideKeyboard(View view) {
        InputMethodManager imm = (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
        if (imm != null) imm.hideSoftInputFromWindow(view.getWindowToken(), 0);
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        webView.saveState(outState);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
            return;
        }
        showUrlDialog(dashboardUrl());
    }

    private class DashboardWebViewClient extends WebViewClient {
        @Override
        public boolean shouldOverrideUrlLoading(WebView view, String url) {
            view.loadUrl(url);
            return true;
        }

        @Override
        public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
            if (request != null && request.isForMainFrame()) {
                showErrorPage(request.getUrl().toString(), error == null ? "Bağlantı xətası" : error.getDescription().toString());
            }
        }

        @Override
        public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
            handler.cancel();
            showErrorPage(view.getUrl(), "SSL sertifikat xətası");
        }
    }
}
