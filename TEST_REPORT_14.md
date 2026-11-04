# Personal Hub 1.4 测试报告（2026-11-04）

## 已实际完成的自动化测试

| 项目 | 通过 | 失败 | 说明 |
|---|---:|---:|---|
| 1.3 继承回归 | 94 | 0 | 历史桥接、监控、网页集成、数据保护、JavaScript 行为；将旧缓存版本断言更新为 v14，并核实原 v13 资源仍存在 |
| 1.4 Python 同步库及 HTTP | 11 | 0 | 身份验证、Origin 拒绝、路径保护、版本 CAS、幂等、文件损坏拒写、历史版本、符号链接、并发与大小上限 |
| 1.4 集成与 Android 静态检查 | 8 | 0 | 新导航/静态资源/SW 缓存、原 app 与 CSS 字节完整、APK 源码独立包名及来源限制、assets 全量匹配 |
| 1.4 纯 JavaScript 合并测试 | 15 | 0 | 首次合并、三方增量、删除、冲突必须人工选择、设置冲突、ID 校验、不依赖属性次序 |
| **合计** | **128** | **0** | `python3 tests/run_all.py` 中实际执行的测试 |

此前的 1.3 回归中有个用例将 Service Worker 版本写死为 `v13`；1.4 升级后已把**测试期望**调整为 `v14`，未跳过或删除原有测试，并仍逐项检查 1.3 的监控资源存在。项目历史代码 `web/app.js` 与 `web/styles.css` 继续与 1.3 完全一致。

## 浏览器交互测试（未通过环境验收）

实际启动 `tests/browser_sync_14.py`，尝试以两套独立 Chromium browser context 访问本机 HTTP 桥；页面导航阶段由环境返回 `net::ERR_BLOCKED_BY_ADMINISTRATOR`。这说明**浏览器端 IndexedDB/按钮/手机同步流程尚未完成自动化验收**，不是 128 项逻辑测试中的通过项目，不将其归咎于已确认的应用代码错误。

## Android 预检（源码静态检查成功，未构建）

运行 `python3 tools/android_preflight_14.py`：测试包名与正式版隔离、不允许 HTTP 明文混合内容、禁用 Android 系统自动备份、资源包校验等项目通过。当前环境有 Java 但**无 Gradle、ADB、apksigner**；未得到任何 APK 或证书比对结果。源码未经过 Android Studio 实际构建，不能据此宣称能够直接安装。

## 未执行、需要真实设备完成

- 荣耀 V9 HarmonyOS 2 浏览器访问电脑 LAN `/hub/`，配对、IndexedDB 读写、首次导入、连续双向同步、相同条目冲突处理、HTTP 隐私风险评估。
- 荣耀 Win11 上的 Web 浏览器及 Python 3.9+ 服务可用性，Mac/Ubuntu 实机运行与前台 AI 输入。
- 用户实际配置的 GitHub 私有仓库/本地 Git/Codex rateLimits/DeepSeek API 账户读取。
- Android Studio Gradle 构建、HarmonyOS WebView 原生文件上传/下载、签名与更新逻辑。
- HTTPS/LAN 安全加密方案（1.4 当前 HTTP 同步属于有风险的受限功能）。

所有测试只在当前容器/本机代码环境执行。若准备使用真实重要资料，请先做好独立的外部加密备份并完成真机验收。
