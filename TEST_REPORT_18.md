# Personal Hub 1.8 — 真实 Java 编译缺陷修复与 APK 发布门禁

## 已核实的回归缺陷

在 1.7 的 `MainActivity.java`，通过新增离线 JDK 主 Activity 编译检查发现：

1. `setupMessageBridge` 的 `catch` 中声明 `String message`，与 WebView `onPostMessage` 回调参数 `message` 重名，导致 Java 编译失败。
2. 该 `catch` 中引用了只在 `try` 内声明的 `id`，不在异常处理作用域内，导致 Java 编译失败。
3. 新的自制 API 编译桩初版缺少 `JSONObject.optBoolean(String)` 重载，产生两条**编译桩误报**；补齐桩后仍存在上面两项真实 Java 源码错误。

1.8 已修复真实的作用域/重名问题，异常回复只在有效请求 ID 可用时发出。没有变更 `web/app.js` 或 `web/styles.css`。

## 验证结果（本轮实际执行）

| 验证项目 | 状态 | 限制 |
| --- | --- | --- |
| JDK 17 编译真实 `MainActivity.java` 和 `PinnedBridgeClient.java` | PASS | 仅用最小 Android/AndroidX API 编译桩，不链接真实 Android SDK |
| 故意破坏 Java 类名，编译必须失败的反向测试 | PASS | 验证检查器可捕获实际 Java 编译错误 |
| Python 回归测试 | PASS（123 项） | 其中含 TLS loopback 测试，但不代表安卓环境 |
| Node.js 前端回归测试 | PASS（50 项） | 不代表系统 WebView 的 UI 验收 |
| 便携测试合计 | **PASS（173/173）** | 不是 173 次 APK 或 V9 真机测试 |
| Android 15 / 16 / 17 原有源码及资源预检 | PASS | 静态预检 |
| Android 资源同步核对 | PASS | 33 份内置网页资源与 `web/` 内容一致 |
| 发布检查器源码模式 | SOURCE_READY | 不等于生成 APK |
| 发布检查器无 APK 普通模式 | 正确拒绝（返回码 2） | 阻止误报签名成功 |
| Gradle + Android SDK 全量编译 | 未执行 | 环境无 SDK/Gradle，DNS 无法解析外部仓库 |
| 实际 APK 的签名与安装测试 | 未执行 | 无 APK，GitHub 连接未列出可用仓库 |
| 荣耀 V9 真机、通知、存储、同步及性能 | 未执行 | 未连接真机 |

## 构建配置变更

- `versionCode`: 4 → 5；`versionName`: `1.7.0-preview` → `1.8.0-preview`；**预览包名保持不变**。
- CI 将 `android-actions/setup-android` 提升为 v4；明确安装 Node 22；加入实际主 Activity 的 Java 编译门禁。
- 完整自动化回归遇到 Node 缺失时改为失败而不是静默略过。
- 添加发布状态命令 `tools/release_readiness_18.py`，需要真实 APK 才可能返回已核验。
- `verify_android_apk.py` 的期望版本同步为 `versionCode=5`，并更新相应回归测试。

## 正式 APK 仍缺哪些条件

参见 `docs/ANDROID_BUILD_18.md`。不能以此 ZIP 替代经过真实 Gradle、aapt、apksigner、荣耀 V9 验证的 APK。
