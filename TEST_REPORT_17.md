# Personal Hub 1.7 · 自动化验证与未验收事项

2026-11-04 | Android APK 原生安全同步及电脑快捷指令累积版

## 已真实执行、通过的测试

- **171/171 项 Python + Node.js 自动化测试通过**：Python 子测试合计 121 项；Node.js 子测试 50 项。最终完整回归运行于 1.7 累积工程目录，进程退出码 0，未跳过 Node 测试，结束日志为 `[PASS] 已执行的全部自动化测试组通过`。
- **新增原生 HTTPS 专项测试 6/6**：将 `PinnedBridgeClient.java` 复制到 ASCII 目录并使用 JDK `javac` 真实编译；通过本地真实 TLS 服务器验证正确指纹下的 HTTPS 请求、配对 Cookie 与后续已配对读取；错误指纹、错误 IP SAN、过期证书和越权管理路径均按预期被拒绝。测试中使用临时生成的证书，未读取用户真实证书。
- **新增 Android 原生桥接 JavaScript 测试 4/4**：验证私网 IP / 端口 / 指纹校验、普通浏览器降级、请求 ID 匹配、配对 Cookie 不暴露给 JS、首次证书固定必须确认。
- **Android 1.7 静态发布预检 19/19**：检查受限的 Android 原生页面访问、禁止 HTTP/未知域名与任意命令 API、IP SAN/指纹验证、后台网络线程、原生数据同步、旧主控保留、构建配置及离线资源。
- **33/33 份 Android 内置公共 Web 资源一致性检查通过**；`web/app.js`、`web/styles.css` 与上版核心文件保持原样。
- 1.5 原生文件入口静态预检、1.6 HTTPS / 加密保险库静态预检、1.6 实际 Python 服务端 TLS 与 AES-GCM 回归以及 APK 产物审核器模拟测试均通过。

## 通过不代表哪些结论？

1. **没有编译出 Android APK**：当前环境缺 Android SDK / Gradle 可下载的构建配置，尚未执行本工程 GitHub Actions；JDK 可编译独立无 Android 依赖的 `PinnedBridgeClient.java`，**不等于 Android `MainActivity.java` 和 WebKit AndroidX 编译通过**。
2. **没有荣耀 V9 真机联网**：尚未证明 HarmonyOS 2 的 System WebView 支持 `WEB_MESSAGE_LISTENER`、原生消息回复、手机 IP SAN 固定策略、数据同步、备份导入、前台键盘注入、后台生存、横屏与续航。
3. **模拟 TLS 服务端 ≠ 真机与实际电脑桥端到端测试**：原生 Java 客户端的网络测试使用临时 Python TLS 服务器；1.6 的真实 Python 电脑桥另有自己的 TLS/会话/加密测试，但两者联合上机尚未执行。
4. **没有验证已装旧 APK 的签名和升级路径**：持续使用隔离包名 `dev.personalhub.v9preview`，`versionCode=4`；debug APK 的不稳定签名不能保证覆盖升级和数据保留。
5. **外部账号和服务未做实测**：Codex 登录额度、DeepSeek 实际余额、GitHub 仓库 Actions、华为健康、电脑真实 AI 窗口输入均未在用户设备/账号验证。
6. **Chromium 浏览器交互**：此前环境导航出现 `ERR_BLOCKED_BY_ADMINISTRATOR`，本轮未将模拟交互当作浏览器真机 PASS。

## 本轮核心安全边界

- 手机输入电脑 IP + **电脑本机独立核对的完整 SHA-256 证书指纹**；没有自动相信未知证书（TOFU）与“忽略证书警告”。
- 请求只访问 allowlist 的电脑 API；JS 不获得 HttpOnly Cookie；WebView 不放开 `usesCleartextTraffic` 或不受限的 `addJavascriptInterface`。
- 电脑已有 1.6 版 HTTPS + 加密数据保险库；手机同步依然经过快照、手动冲突确认、CAS 和本机回读。
- 发送 AI 文字前电脑需要授权允许的前台窗口；网页中的勾选仅减少重复确认，不替代电脑本机授权。

## 发布前必做验收（阻断项）

- 在真实 GitHub CI 或本地 Android SDK 构建 APK 并运行 `verify_android_apk.py`；实际 `aapt/apksigner` 校验签名、版本、包名和 assets 字节。
- 荣耀 V9 + 电脑在可信局域网实测：证书绑定与拒绝不匹配 → 临时 PIN 配对 → 本机记录同步与冲突 → 断网重连 → 恢复快照 → 快捷指令真实电脑窗口输入。
- 先核对旧 APK 包名和签名；如不满足升级条件，必须按导出/导入方式迁移且保留旧版，不能静默替换。

**结论：1.7 源码级功能及可在此环境执行的安全回归通过；正式 APK 和荣耀 V9 真机验收仍未完成。**
