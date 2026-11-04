# Personal Hub 1.5 · 自动化回归与兼容性边界（2026-11-04）

## 测试概览

- **通过：143 / 143** 已运行自动化测试（Python `unittest` 97，Node `node --test` 46）。
- Android 独立静态预检：`tools/android_preflight_15.py` 的 **13 / 13** 条静态规则及 30 个 Android assets 对齐检查通过；这些不属于上面 143 项测试的重复计数。
- 1.4 原始业务 JS 已作为 `tests/fixtures/web_app_v14.js` 归档；`tests/compat15.py` 核对除了 `exportBackup()` 导出函数外，没有更改任何业务主程序文本；styles.css SHA256 仍与 1.4 一致。
- 原电脑桥配对、权限、队列、事件、同步写入及并发冲突测试全部随 `tests/run_all.py` 回归执行。
- 新增 `tests/native_15.test.js`：测试文件名/JSON 校验、Native 消息回调、取消拒绝、未知请求不误解析、设备设置和左右滑动模块边界。
- 新增 `tests/native_15_test.py`：核对 HTML 资源、入口加载顺序、文件写入成功语义、JNI API 白名单、显示设置和 Android assets 镜像。

### 如何重跑

在解压后的工程根目录执行：

```bash
python3 tools/sync_android_assets.py --check
python3 tools/android_preflight_15.py
python3 tests/run_all.py
```

Node 缺失时，脚本会跳过 JavaScript 测试，不能宣称仍通过 143 项。部分历史测试会打印模拟安装器的预期 `[FAIL]` 字样，用于确认文件冲突被安全拒绝；这并不等于 Python suite 失败，应以各组 `Ran X tests / OK` 和最终进程退出码为准。

### 真实浏览器测试：未通过环境验证

实际运行：`python3 tests/browser_sync_14.py`。

结果：`Page.goto: net::ERR_BLOCKED_BY_ADMINISTRATOR at http://127.0.0.1:<随机端口>/hub/`。属于当前 Chromium 环境阻断本地地址的策略，未观察到应用正常加载；不能据此断言浏览器端合并功能正确，也不能判定它存在浏览器逻辑故障。此项标为**未验收**。

### Android 与硬件：尚未执行

- 没有在当前环境调用 Android Gradle 构建器、SDK、ADB 或 apksigner；只生成工程源码和 `.github/workflows/android-preview.yml`。尚未下载、编译、安装或签名 APK。
- JNI/WebViewCompat 的签名与来源规则已参考 AndroidX 官方文档进行代码核查，但 Java 编译以及厂商 WebView 行为仍必须在 Android CI / 荣耀 V9 上确认。
- 未测试真实 V9 SAF 导出恢复、IndexedDB、Web Crypto、弹框、横屏翻页、24h 发热/耗电、任务栏返回键、杀后台数据持久化。
- Codex、DeepSeek 的实际授权 API 调用未执行，未上报任何伪造的真实余额/任务成功率。

## 具体交付范围和遗留风险

- **已做**：系统文件选择器源码、双重校验流程接线、原生只限本地来源的 JS 消息、默认关闭常亮、横屏滑动、受限 HTTPS GitHub API、一次性手动 Android CI 工作流、资产同步工具。
- **保留风险**：局域网 HTTP 同步及电脑侧磁盘同步数据未加密；无法在内置 APK 中直接同步，仍通过外部浏览器操作。无真实系统通知权限与后台调度，不保证屏幕关闭后实时提醒。
- **重要数据警示**：原 APK 的包名/证书未知，不可将预览 APK 直接视为原应用的无损升级。保存唯一重要数据前先做外部加密备份并核实可恢复。
