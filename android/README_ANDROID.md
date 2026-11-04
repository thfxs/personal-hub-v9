# 1.8 更新

`MainActivity.java` 已通过新增的 JDK 17 最小 Android API 编译桩检查，并修复了 1.7 的两个实际 Java 作用域错误。预览包 `versionCode=5` / `1.8.0-preview`；Android SDK/Gradle **真实构建尚未完成**。构建说明见 `../docs/ANDROID_BUILD_18.md`。

---

# Personal Hub 1.5 · Android 原生预览工程

**不是已经编译的 APK，也不是可以覆盖现有荣耀 V9 应用的正式升级包。** 当前包名 `dev.personalhub.v9preview` 用于隔离测试，不会自动获得现有 APK、浏览器或 GitHub Pages 的 IndexedDB 数据。

## 本次补齐

1. 使用 AndroidX WebViewAssetLoader 的 `https://appassets.androidplatform.net/assets/web/` 提供离线 HTML、JS、CSS。默认沉浸模式；可在「手机设备与屏幕」设置里关闭。常亮默认关闭。
2. AndroidX `WebViewCompat.addWebMessageListener` 注册**限制到唯一 HTTPS 来源、主框架**的原生消息通道，不暴露全局 `addJavascriptInterface`。只有用户主动点击导出，才通过 `ACTION_CREATE_DOCUMENT` 打开 Android 系统文件选择器，等用户选定路径、写入 JSON 完成以后才反馈成功。单文件最多 4MiB；超过限制会拒绝，不截断。
3. 通过 `ACTION_OPEN_DOCUMENT` 的文件输入恢复 JSON；仍走现有前端的预览、校验、双确认和恢复前快照。选择器取消会安全终止，不承诺用户授权之外的文件访问。
4. 在 WebView 不支持 `WEB_MESSAGE_LISTENER` 时会显示降级提醒，**不会把无效 Blob 下载冒充成功备份**；必须升级 System WebView 或改用已验证的外部备份方式。
5. 限制 WebView 额外网络请求：仅放行公开 GitHub Actions 状态的 HTTPS GET 读取，不发送私人 API Key；其他外部 HTTP(S) 页面跳转由系统浏览器打开。仍然**没有**内置 APK 的可信加密局域网同步通道；1.4 的 HTTP 桥仍只能通过外部浏览器手动访问。

## 如何用 GitHub Actions 建立测试 APK（无需本地 Android Studio）

上传此整包**文件夹内容**到你自己的 GitHub 仓库，保持根目录 `.github/workflows/android-preview.yml` 和 `android/`、`web/` 一同存在。在 Actions 标签页选择 `Personal Hub V9 - manual Android build` → `Run workflow` → `debug`。工作流会在 CI 安装 Android SDK 35 和 Gradle 8.13，先检查内置资源与源码，再构建 debug APK 并作为 artifact 上传。

**注意**：CI 生成的 debug 证书是临时的；不同构建之间签名可能不同，绝对不要指望 debug APK 原地覆盖升级而保留数据。这个工作流尚未在你的仓库实际运行。暂时不需要安装测试 APK。

如果未来需要可以持续升级的签名测试版，可以用 Android `keytool` 在你可信电脑上一次性生成自己的签名证书，私钥**必须长期离线备份**。在 GitHub Actions Secrets 设置 `PH_KEYSTORE_B64`、`PH_STORE_PASSWORD`、`PH_KEY_ALIAS`、`PH_KEY_PASSWORD`，再选择 `release`。release 使用同一密钥才可能覆盖升级；若丢失证书或修改 `applicationId`，就无法保证原数据可迁移。请勿把 `.keystore`、密码、私密 JSON 上传仓库或聊天。工作流目前没有被执行、生成 APK 或验证签名。

你曾经安装的旧 APK 包名/签名仍未知：**在没有核对之前，绝不强行替换。** 这轮继续按原定计划累积工程，最后统一签名并实机安装验收。

## 构建前检查

在工程根目录执行：

```bash
python3 tools/sync_android_assets.py --check
python3 tools/android_preflight_15.py
python3 tests/run_all.py
```

如果修改了 `web/` 文件，先运行 `python3 tools/sync_android_assets.py` 更新 `android/app/src/main/assets/web`，再提交 Git 仓库。构建前检查会拒绝网页与 APK 资源不一致。

## 尚未验证

- 未在当前环境中安装 Gradle、Android SDK、ADB、签名工具；没有 Java/Android 编译结果，更没有实际 APK。
- 荣耀 V9 HarmonyOS 2 的系统 WebView 版本、WebMessageListener 支持、SAF 文件读写、杀后台恢复、不同屏幕方向需要真机验证。
- 不保证后台常驻、锁屏通知或跨应用自动获知 AI 对话完成；APK 内部 HTTP 局域网同步仍处于禁用状态。

## 1.6 补充：构建后发布门禁

- `compileSdk=36`、`targetSdk=35`、`minSdk=26`，独立测试包 `dev.personalhub.v9preview`，版本号 `1.6.0-preview` / `versionCode=3`。
- CI 中必须通过 `tools/verify_android_apk.py` 对**实际生成的** `.apk` 检查包名、版本号、V2 签名、SHA256 和内置 Web 资源；检查失败不得将 APK 称作已验收产物。
- CI 若选择 release，需在仓库 secrets 内存在四项自有签名配置。密钥仅供 CI 生成签名测试版；不能替代核对原 APK 签名。必须保存自己的证书，并避免交叉使用临时 debug 签名。
- 本轮电脑桥已准备 HTTPS 和加密保险库，**但 Android 内置 WebView 仍然不直接使用 TLS 私有证书访问电脑**。不可因为服务器支持 HTTPS 就宣称 Android APK 已经完成安全双向同步；需要后续明确设计和测试证书信任/指纹绑定。
- 当前环境缺少可下载的 Android SDK 与 Gradle 分发包，GitHub 连接也未列出仓库。因此本轮没有产生、下载或安装 APK。

## 1.7 追加：APK 内原生 HTTPS 客户端

- Java 文件 `PinnedBridgeClient.java` 使用用户手动核实的电脑端证书 SHA-256 作为唯一显式固定信任锚，并额外检查 IP SAN / 到期日；不使用 TOFU 自动接受，不允许忽略证书错误，也不会放开 WebView 混合内容。
- 通信通过 `WebViewCompat.addWebMessageListener`，限制 HTTPS appassets 可信 origin、主框架，且只允许内置 `sync/index.html` 和 `remote.html` 调用电脑桥。会话 Cookie 留在 Java 内存，配置变化或 APP 重启后需要重新配对。
- 真实 Android SDK 编译和真机可用性**仍未验收**。纯 JDK TLS 通信测试通过不等于 V9 系统 WebView/Android TLS 提供者一定具有相同表现。
- `versionCode=4`，`versionName=1.7.0-preview`；保持独立测试包名。首次安装不会继承已安装的旧包数据；按 `docs/SECURITY_SYNC_17.md` 的说明先核对备份。
