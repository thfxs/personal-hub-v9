# Personal Hub 1.8 — 实际 APK 构建与一次性验收说明

## 本轮状态：源码可编译检查通过，正式 APK 仍未生成

- ✅ 主 `MainActivity.java` / `PinnedBridgeClient.java` 通过 **JDK 17 + Android API 编译桩** 的源码类型/语法编译；这是对 1.7 只编译 HTTPS 客户端测试缺口的补足。
- ✅ 完整旧业务与安全回归测试、前端与 Android 内置资源一致性检查通过。
- ✅ CI 文件中安装对应 Java、Python、Node、Gradle、Android SDK，在构建后使用 `aapt` / `apksigner` 复核版本、资源和签名。
- ⛔ 本次执行环境缺少 Android SDK、Gradle；本地 DNS 也无法解析 Google/Gradle 资源域名。
- ⛔ 当前已关联的 GitHub 接口未列出可以直接操作的仓库，因此没有在 GitHub Actions 上运行构建。
- ⛔ 没有编译出的 APK；更没有在荣耀 V9（HarmonyOS 2.0）上的存储、前台输入、HTTPS 证书固定等真机结论。

`SOURCE_READY` 表示**源码层面的就绪**；不代表 `APK_ARTIFACT_VERIFIED` 或者 `V9_ACCEPTED`。

## 如何在 GitHub Actions 完成真正构建（无需在手机上提前安装）

1. 在自己的 GitHub 仓库（建议**私有**，避免把尚未发布的源码公开）上传本 ZIP **解压后根目录的全部文件**，保留 `.github/workflows/android-preview.yml` 隐藏目录，不要上传 `.env`、备份 JSON、密钥、`vault-passphrase.txt`。上传后检查仓库根目录能看到 `android/`、`web/`、`bridge/`、`tools/`、`tests/` 与 `.github/workflows/android-preview.yml`。
2. 到仓库 **Actions → Personal Hub V9 - manual Android build → Run workflow → debug**，执行首次真实编译。Debug 只用来核验工程能否通过 Android SDK 构建，**暂时不要在 V9 安装**，避免和旧版本签名/包名混淆。
3. 成功后在 Actions 运行页下方找 `personalhub-v9-debug-preview-1_8`，核对构建日志中 `assembleDebug` 与 `verify_android_apk.py` 都通过，再下载 APK 及 SHA256 进行存档。如果工作流失败，以实际失败的 Gradle/SDK 日志为准，不能依据之前的 173 项离线测试声称 APK 可用。
4. 决定正式签名与旧版迁移路径后，才运行 `release`。四个签名 Secrets `PH_KEYSTORE_B64` / `PH_STORE_PASSWORD` / `PH_KEY_ALIAS` / `PH_KEY_PASSWORD` 只在 GitHub **仓库 Secrets** 中设定，私钥不要上传源码或发送到对话。若旧版已经安装，必须核对包名和旧签名；不要为原地覆盖旧版临时重造密钥。
5. 真正装 V9 前，在电脑保存旧版外部备份，再核对 `tools/check_android_upgrade.py` 所需的旧版本、签名和实际构建输出。此测试工程包名固定 `dev.personalhub.v9preview`，**不会自动继承旧 APK 或 PWA 的 IndexedDB 数据**。

构建系统的版本：Android Gradle Plugin 8.13.2、Gradle 8.13、Java 17、compileSdk 36、minSdk 26、targetSdk 35、AndroidX WebKit 1.18.0。此处使用匹配的官方 Gradle/AGP 版本，不为了追求最新版而改动业务代码。

## 本地源码检查与构建门禁

```bash
python3 tools/release_readiness_18.py --source-only
python3 tests/run_all.py
```

真正获得 APK 且本机安装了 Android SDK Build Tools 后：

```bash
python3 tools/release_readiness_18.py --apk android/app/build/outputs/apk/debug/app-debug.apk \
  --build-tools "$ANDROID_SDK_ROOT/build-tools/35.0.0"
```

无实际 APK 时，上一个命令会以非零状态码失败，不会生成虚假的验收报告。Debug 的临时签名不保证可跨 CI 运行覆盖升级。

## 完成正式版必须取得的外部证据

- Android SDK 真实 Gradle 构建成功日志与 `.apk` 产物。
- `aapt` 包名、versionCode、minSdk/targetSdk 和 `apksigner` V2 签名校验通过。
- 旧版手机应用的真实 `applicationId`、签名、存储 origin；决定覆盖或并行安装及备份迁移。
- 荣耀 V9 真机 WebView 安全消息通道支持、SAF 导出/恢复、横屏滑动、离线保存和返回后恢复。
- 手机对真实电脑 HTTPS 指纹确认、双向合并、断网、证书错误拒绝和电脑 AI 窗口受控输入。

**现在仍不需要在手机安装或卸载任何版本**。
