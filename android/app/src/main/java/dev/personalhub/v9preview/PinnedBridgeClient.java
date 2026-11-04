package dev.personalhub.v9preview;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;
import java.util.Collection;
import java.util.List;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;

/**
 * Minimal, single-host, explicit certificate-pinned LAN HTTP client.
 * This class intentionally has no Android dependency so its TLS handshake can
 * be exercised with the normal JDK during the build. It never falls back to
 * cleartext or a user-clickable TLS error bypass.
 *
 * The SHA-256 pin MUST be copied from the computer's local certificate setup
 * output through an independent channel before making the first request.
 * A certificate rotation requires explicit re-pinning; no silent TOFU.
 */
public final class PinnedBridgeClient {
    private final String ip;
    private final int port;
    private final String fingerprint;
    private String cookie = ""; // Memory only, never returned to JS or stored to disk.
    public static final int MAX_RESPONSE_BYTES = 2 * 1024 * 1024;

    public static String validateIP(String input, boolean allowLoopback) {
        if (input == null || !input.matches("[0-9]{1,3}(\\.[0-9]{1,3}){3}"))
            throw new IllegalArgumentException("只接受局域网 IPv4 数字地址");
        String[] fields = input.split("\\.");
        int[] a = new int[4];
        for (int i=0; i<4; i++) {
            a[i] = Integer.parseInt(fields[i]);
            if (a[i] > 255) throw new IllegalArgumentException("IP 不合法");
        }
        boolean lan = (a[0] == 10) || (a[0] == 172 && a[1] >= 16 && a[1] <= 31)
            || (a[0] == 192 && a[1] == 168);
        boolean loopback = allowLoopback && a[0] == 127 && a[1] == 0 && a[2] == 0 && a[3] == 1;
        if (!lan && !loopback) throw new IllegalArgumentException("只允许私有局域网 IP");
        return a[0] + "." + a[1] + "." + a[2] + "." + a[3];
    }

    public static String validateFingerprint(String input) {
        if (input == null) throw new IllegalArgumentException("必须填写证书 SHA-256 指纹");
        String clean = input.replace(":", "").replace(" ", "").toUpperCase(java.util.Locale.ROOT);
        if (!clean.matches("[0-9A-F]{64}"))
            throw new IllegalArgumentException("证书指纹必须是 64 位 SHA-256 十六进制字符");
        return clean;
    }

    public PinnedBridgeClient(String ip, int port, String fingerprint, boolean allowLoopback) {
        this.ip = validateIP(ip, allowLoopback);
        if (port < 1024 || port > 65535) throw new IllegalArgumentException("端口需为 1024～65535");
        this.port = port;
        this.fingerprint = validateFingerprint(fingerprint);
    }
    public String getIP() { return ip; }
    public int getPort() { return port; }
    public String getFingerprint() { return fingerprint; }

    private SSLContext context() throws Exception {
        X509TrustManager pinned = new X509TrustManager() {
            @Override public void checkClientTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                throw new CertificateException("客户端证书检查不用于此连接");
            }
            @Override public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
            @Override public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                if (chain == null || chain.length == 0 || chain[0] == null) throw new CertificateException("无服务器证书");
                X509Certificate leaf = chain[0];
                leaf.checkValidity();
                try {
                    byte[] digest = MessageDigest.getInstance("SHA-256").digest(leaf.getEncoded());
                    byte[] target = fromHex(fingerprint);
                    if (!MessageDigest.isEqual(digest, target)) throw new CertificateException("电脑证书指纹不匹配，连接已拒绝");
                    // An exact certificate fingerprint is the explicit trust anchor.
                    // Additionally require IP SAN to match the configured literal IP.
                    boolean ipMatches = false;
                    Collection<List<?>> names = leaf.getSubjectAlternativeNames();
                    if (names != null) for (List<?> entry : names) {
                        if (entry.size() >= 2 && Integer.valueOf(7).equals(entry.get(0))
                            && ip.equals(entry.get(1))) ipMatches = true;
                    }
                    if (!ipMatches) throw new CertificateException("证书没有匹配的电脑 IP SAN");
                } catch (java.security.cert.CertificateEncodingException | NoSuchAlgorithmException exc) {
                    throw new CertificateException("无法验证证书指纹", exc);
                }
            }
        };
        SSLContext ctx = SSLContext.getInstance("TLS");
        ctx.init(null, new TrustManager[] {pinned}, null);
        return ctx;
    }
    private static byte[] fromHex(String s) {
        byte[] out = new byte[s.length()/2];
        for(int i=0; i<out.length; i++)out[i]=(byte)Integer.parseInt(s.substring(i*2,i*2+2),16);
        return out;
    }
    private static void allow(String method, String path) {
        boolean get = "GET".equals(method) && ("/api/status".equals(path)
            || "/api/sync".equals(path) || "/api/monitor".equals(path)
            || "/api/events".equals(path) || "/api/queue".equals(path));
        boolean post = "POST".equals(method) && ("/api/pair".equals(path)
            || "/api/sync".equals(path) || "/api/dispatch".equals(path)
            || "/api/events/read".equals(path));
        if (!get && !post) throw new IllegalArgumentException("请求路径不在白名单中");
    }
    private static byte[] readLimit(InputStream in) throws IOException {
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        byte[] block = new byte[8192];
        int n;
        try (InputStream stream = in) {
            while ((n=stream.read(block)) != -1) {
                if (buf.size() + n > MAX_RESPONSE_BYTES) throw new IOException("电脑响应过大，连接已停止");
                buf.write(block, 0, n);
            }
        }
        return buf.toByteArray();
    }
    public synchronized Response request(String method, String path, String json) throws Exception {
        allow(method,path);
        byte[] body = "POST".equals(method) ? (json == null ? "{}" : json).getBytes(StandardCharsets.UTF_8) : new byte[0];
        int max = "/api/sync".equals(path) ? 1_500_000 : 4096;
        if (body.length > max) throw new IOException("提交数据超过电脑桥限制");
        HttpsURLConnection c = (HttpsURLConnection) new URL("https://"+ip+":"+port+path).openConnection();
        try {
            c.setSSLSocketFactory(context().getSocketFactory());
            // Certificate IP SAN validation is performed by the pinned trust manager.
            c.setHostnameVerifier((hostname,session)->ip.equals(hostname));
            c.setConnectTimeout(5000);
            c.setReadTimeout(12000);
            c.setUseCaches(false);
            c.setInstanceFollowRedirects(false);
            c.setRequestMethod(method);
            c.setRequestProperty("Accept", "application/json");
            if (!cookie.isEmpty()) c.setRequestProperty("Cookie", "phb_session="+cookie);
            if ("POST".equals(method)) {
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                c.setRequestProperty("X-Bridge-Request", "1");
                c.setFixedLengthStreamingMode(body.length);
                try (OutputStream out=c.getOutputStream()) {out.write(body);}
            }
            int status=c.getResponseCode();
            if (status >= 300 && status < 400) throw new IOException("不允许电脑桥跳转到其他地址");
            String setCookie = c.getHeaderField("Set-Cookie");
            if ("/api/pair".equals(path) && status == 200 && setCookie != null) {
                java.util.regex.Matcher m=java.util.regex.Pattern.compile("(?:^|;\\s*)phb_session=([A-Za-z0-9_-]{20,160})(?:;|$)").matcher(setCookie);
                if (m.find()) cookie=m.group(1);
            }
            InputStream in=status >= 400 ? c.getErrorStream() : c.getInputStream();
            if (in==null) throw new IOException("电脑未返回内容");
            String raw=new String(readLimit(in),StandardCharsets.UTF_8);
            if (!raw.trim().startsWith("{")) throw new IOException("电脑返回非 JSON 内容");
            return new Response(status,raw);
        } finally {c.disconnect();}
    }
    public static final class Response {
        public final int status;
        public final String json;
        public Response(int status,String json) {this.status=status;this.json=json;}
    }
}
