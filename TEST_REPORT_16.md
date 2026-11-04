# Personal Hub 1.6 · 自动化验证记录（2026-11-04）

## 已执行的代码测试

- 保留 1.5 的原始 143 项 Python/Node 自动化测试。
- 新增 1.6 安全桥共 13 项：真实 TLS 握手、信任证书后配对、Cookie Secure、错误 Origin 拒绝、未信任证书握手失败、AES-256-GCM 加密落盘、历史加密、文件篡改、旧明文模式拒绝、密码文件链接与权限检查、证书生成幂等、证书/私钥不匹配拒绝、五个独立进程竞争写入。
- 新增 1.6 APK 验证器 5 项：APK 内置资源完整性、缺失或夹带隐私文件拒绝、源码/资源不符拒绝、模拟 Android SDK 工具的签名/包名检查、签名或包名错误拒绝。
- 合计应为 **161 项**（完整 `tests/run_all.py` 重新执行并核对输出后方确认）。
- Android 静态检查另列 `tools/android_preflight_15.py`（13 条）与 `tools/android_preflight_16.py`（17 条），以及 APK/PWA 同源静态资源 30 个；不将静态检查混入 161 项代码测试数量。

## 真实 TLS / 电脑磁盘

用 Python `ssl` 以证书文件作为信任根，实际打开本地 HTTPS 服务器并执行 HTTPS PIN 配对、`Secure; HttpOnly; SameSite=Strict` cookie、GET/POST 同步，服务器写入 AES-GCM 密文并核对内容。错误密码或被篡改加密文件拒绝写入，测试确认失败不会覆盖原文件。独立 Python 进程并发验证同一初始修订最多一个可提交。与全部设备联网后的长期稳定性测试不同。

## Chromium 真实浏览器

运行 `python3 tests/browser_sync_14.py`：

```text
[BROWSER NOT PASSED] Error Page.goto: net::ERR_BLOCKED_BY_ADMINISTRATOR
at http://127.0.0.1:<随机端口>/hub/
```

浏览器测试被当前测试环境管理策略阻拦，不能据此判定业务 JS 在真实浏览器中已通过，也不能据此推断是产品逻辑失败。标记：**未验收**。

## Android / APK / 真实手机

- 当前环境仅有普通 JDK/Node/Python，不具备 Android SDK 和 Gradle 分发包，并且不能从下载域名解析依赖。因此未运行 Gradle `assembleDebug/Release`，未生成 APK。
- 未在可用 GitHub 连接里找到用户的可操作仓库，未触发真实 GitHub Actions；仅对 workflow 源码编写和静态核对。
- `tools/verify_android_apk.py` 测试使用构造的 APK ZIP 和模拟 `aapt` / `apksigner` 输出，**不是实际 APK 签名已验证**；CI 在真实 APK 生成之后才执行真正核验。
- 荣耀 V9 原安装包名和签名尚未提供，不能判断其是否能被覆盖升级。Android WebView 安全文件接口仍未真机验证；内置 APK 与电脑之间的无感 HTTPS 同步尚未实现，证书信任配置未在手机上完成。

## 安全警示

默认禁用远程 HTTP 数据同步，旧版明文同步文件不会被自动覆盖；这是防止泄露数据的兼容性限制，不应为了恢复连接而关掉。Android APK 不直接接入未经信任的局域网服务。第一次实机同步前务必在来源应用导出经过核验的备份，切勿卸载或覆盖保存有唯一数据的旧 APK。
