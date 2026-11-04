# Personal Hub V9 · 1.8 构建就绪与 APK 发布验证（完整累积工程）

> 这是 **完整累积源码**，不是可安装 APK。新增真实 Java 源码编译检查，修复了 1.7 `MainActivity.java` 的两个真实作用域编译错误。官方 Android SDK 构建及荣耀 V9 真机测试尚未完成。原有业务功能和 HUD 风格保留。

## 1.8 关键结果

- JDK 17 编译 `MainActivity.java` 与 `PinnedBridgeClient.java` 通过（使用最小 Android 编译桩）；故意引入 Java 源码错误时检查器能正确拒绝。
- 便携自动化回归：**173/173 PASS**（Python 123 / Node.js 50）；资源核对 **33 个 PASS**。
- 新增 `tools/release_readiness_18.py`，将 `SOURCE_READY` 与真实的 `APK_ARTIFACT_VERIFIED` 严格区分；无 APK 的普通模式返回失败。
- `versionCode=5`, `1.8.0-preview`，仍是独立测试包 `dev.personalhub.v9preview`，**不可假定覆盖旧 APK 或自动继承数据**。
- GitHub Actions 已同步升级安装步骤、Node、主 Activity 编译门禁；但目前尚无可调用的仓库、Android SDK 和真实构建日志，因此未生成 APK。

**请先看 [docs/ANDROID_BUILD_18.md](docs/ANDROID_BUILD_18.md) 和 [TEST_REPORT_18.md](TEST_REPORT_18.md)。现在不需要在荣耀 V9 安装。**

---

# Personal Hub V9 · 1.7 原生安全同步与电脑快捷指令完整累积工程

> **这是完整累积源代码工程，不是已编译的 APK，不是荣耀 V9 真机验收通过的正式版。** 1.7 在 1.6 全量源码上直接演进，保留 0.1 主控以及 0.9～1.6 的已集成功能。0.6～0.8 原始源码仍未找回，1.3 依照已知需求重新实现的监控、额度和事件功能不是对旧文件的恢复。

## 1.7 一次完成的内容

1. **APK 原生 HTTPS 安全客户端**：单一电脑 IPv4 / 端口、手动核对完整证书 SHA-256、IP SAN 与有效期验证、拒绝无效证书、拒绝 HTTP 与跳转、路径白名单、网络 IO 在独立后台线程。安卓 WebView 不直接暴露任意内网 HTTP 请求。
2. **APK 直接同步本机数据**：`web/sync/index.html` 根据运行环境在原电脑桥同源网页同步与 Android 原生通道之间切换；新通道直接读取 APK 同一 WebView 源下的 IndexedDB（必要时 localStorage 回退），保留三方合并、删除识别、用户冲突选择、手动确认、本地快照、电脑 CAS 版本校验；本地同步基线按电脑 IP、端口和证书指纹隔离。
3. **APK 原生电脑快捷指令**：新 `web/remote.html` 直接在应用内配对、发「继续」「下一步」「检查」「修复」「完整代码」「总结」「暂停」和自定义指令；调用仍受电脑本机授权、前台 AI 窗口白名单及重复指令策略约束。额外可主动读取电脑端 GitHub、项目、Codex、DeepSeek 和任务上报状态。
4. **本机证书信息工具**：`tools/show_bridge_fingerprint.py` 仅读取电脑本地现有公开证书，展示 SHA-256、IP SAN、到期时间，不读取私钥、不连接网络、不自动更换证书。
5. **1.7 构建门禁**：预览包维持 `dev.personalhub.v9preview` 独立包名，版本提升到 `versionCode=4` / `1.7.0-preview`；CI 增加 Python/加密依赖准备、原生客户端预检和强制构建后签名检查；预览版无法证明可无损覆盖当前手机旧 APP。
6. **继承**：原主控 CRUD、HUD 视觉风格、左/右滑动、沉浸式、SAF 导入导出、加密备份、电脑端 HTTPS+AES-GCM 保险库、项目监控、Agent 额度、事件中心、离线缓存均保留。核心 `web/app.js` 和 `web/styles.css` 未被修改。

## 在电脑上复核源代码

```bash
python3 tools/sync_android_assets.py --check
python3 tools/android_preflight_15.py
python3 tools/android_preflight_16.py
python3 tools/android_preflight_17.py
python3 tests/run_all.py
```

`tests/run_all.py` 包含 Python 代码/HTTP 检查与 Node.js 测试；新增 1.7 Java 客户端的 JDK 编译和真实 loopback TLS 握手测试。Android SDK 与 AndroidX 仍不可用的当前执行环境无法编译 `MainActivity` 或生成 APK。**JDK 的纯 Java 工具类编译通过，不代表 Android 项目 Gradle 构建通过。**

## Android APK 构建（需实际运行）

代码已包含 `.github/workflows/android-preview.yml`，需要把整个工程目录结构放进你自己可运行 Actions 的仓库，再手动选择 debug（临时签名，仅用于功能测试）或 release（需自己的固定签名 Secrets）。CI 会安装 Android 构建工具、运行检查，实际生成 APK 之后运行 `tools/verify_android_apk.py`；任何环节失败不得标作可安装正式版。

**不要直接覆盖已安装的 Personal Hub，也不要在没有外部备份的情况下卸载旧 APK。** 当前尚无历史 APK 的包名/签名证据，也没有任何真实 V9 的构建、升级或 TLS 配对测试记录。

## 手机端配置提示

首次验证真实联调时（不是现在必须安装）：电脑安全启动并运行 `py -3 tools/show_bridge_fingerprint.py`（Windows）或 `python3 tools/show_bridge_fingerprint.py`（Mac/Linux），再在 V9 的「多设备同步」页手动输入电脑 IPv4、端口和证书指纹，勾选已在电脑本机核对，然后输入电脑端 8 位临时配对码。原生接口拒绝不匹配/过期证书。详细步骤和数据迁移边界见 `docs/SECURITY_SYNC_17.md`。

## 当前仍待真正完成

- GitHub Actions 在用户实际仓库运行、Gradle 编译、签名 APK 的真实产物及 Android SDK 的严格门禁校验。
- V9 真机 System WebView 消息接口、SAF、数据库持久化、实机局域网证书固定与双端合并、电脑实际 AI 窗口输入测试、离线、发热与长时间运行验收。
- 旧 APK 包名与签名核对、明确迁移后才能决定是否具备无损升级条件。孤立的 debug APK 不能承诺原地升级。
- 华为健康官方自动获取、对所有网页 AI 任务的自动完成检测没有实现；不得误导为已完成。

见 `TEST_REPORT_17.md`、`VERSION_MATRIX.md`、`docs/SECURITY_SYNC_17.md`。
