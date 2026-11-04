# Personal Hub 1.2 · 测试验收记录（2026-11-04）

| 测试项 | 结果 | 备注 |
|---|---|---|
| 继承 1.1 原有自动化 | PASS 56/56 | HTTP 配对/安全/重试、任务活动、资源集成、升级检查、0.9 加密与校验 |
| 1.2 新增 Web 工程检查 | PASS 7/7 | 静态路径、离线资源、基础代码字节不变、安装幂等与冲突、HTTP 静态 200 |
| 1.2 局域网跳转地址校验 | PASS 3/3 | RFC1918/loopback、拒绝公网 IP、端口输入验证 |
| **自动化测试合计** | **PASS 66/66** | 逻辑、HTTP 测试；不是 V9 真机 |
| HTTP 静态可用性 | PASS | Python urllib 获取 7 个主要资源返回 200 |
| 浏览器 Chromium 页面导航 | **BLOCKED** | 当前沙盒 `net::ERR_BLOCKED_BY_ADMINISTRATOR`；尝试 localhost 及路由模拟域名均被策略阻止 |
| 荣耀 V9 HarmonyOS 2 / 安卓 APK | **NOT RUN** | 未接入手机或原生工程 |
| Windows/Mac 前台 AI 注入 | **NOT RUN** | 未在真实桌面窗口模拟按键 |
| 0.6～0.8 源码集成 | **NOT RUN** | 目前只有功能描述，没有原始源码 |

校验：ZIP 所有资源与 SHA256_MANIFEST.txt 各条哈希一致，压缩包 CRC 自检通过；Web 目录静态页面及 JS/CSS/图标完整。

**隐私**：PC bridge/server.py 只在用户电脑解压后使用。公开部署只应使用 `web/`；不要把源码包整个目录直接上传到 GitHub Pages。
