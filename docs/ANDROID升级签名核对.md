# Android APK 稳定签名与数据不丢失核对（0.9）

当前没有取得 **0.8 Android Gradle 源码、旧版 APK、旧版签名密钥**，因此不能声称“0.9 已稳定签名”或“荣耀 V9 已确认无损升级”。这是可执行的安全门槛，避免因错误签名覆盖失败、卸载重装后丢数据。

## 初次发布与后续升级的区别

- 如果尚未在 V9 安装过正式版本：选定并**永久保持** `applicationId`，首次正式版 `versionCode >= 1`；创建长期安全存储的 release 签名密钥。密钥由用户本地生成与管理，**绝不**提交 GitHub、微信、聊天附件。
- 如果已经安装过旧版：必须用旧版**相同的** `applicationId`、**相同的**签名证书，且新版 `versionCode` 严格递增。新生成的 keystore 不能替代旧版签名；丢失旧版密钥就不能保证正常覆盖升级。
- 浏览器/PWA 与 Android WebView 存储作用域不同；从浏览器迁入 APK 需要先导出备份再导入，不能假设手机会自动迁移数据。

## 本地检查

```bash
python3 tools/check_android_upgrade.py --project /path/to/PersonalHubAndroid --baseline /path/to/installed-baseline.json
```

首次确认旧版工程后，可通过 `--record-baseline /path/to/installed-baseline.json` 记录包名与版本号；该文件**必须对应实际已安装版本**，否则比对没有意义。可同时传 `--installed-apk old.apk --candidate-apk new.apk`；安装有 Android SDK `apksigner` 时，核对两份 APK 的签名证书 SHA-256。未找到 `apksigner` 只会警告，**不代表证书匹配**。

## 生成长期签名密钥（仅首次正式发布；已装正式旧版绝对不要执行来替代旧版密钥）

```bash
mkdir -p "$HOME/.personal-hub-signing"
keytool -genkeypair -v -keystore "$HOME/.personal-hub-signing/release.jks" \
  -alias personalhub -keyalg RSA -keysize 3072 -validity 10000
```

Gradle 推荐从 **本机环境变量或本机不入库的 `~/.gradle/gradle.properties`** 读取路径与密码，不要写在 `build.gradle(.kts)` 或 `gradle.properties`（工程目录）并上传。按项目是 Groovy/Kotlin DSL 将现有 release `signingConfig` 指向**同一个** `release.jks` 与 alias。旧版已安装时以旧版签名为准。

> 有两个不同的凭证：APK 签名密钥与数据备份加密密码。丢失任意一个都可能造成严重恢复问题，务必在受信任离线设备保存安全副本。

## 升级前后验收

1. 从手机上的 0.8 “数据保护中心”制作本地快照，并加密导出到另一台电脑；实际打开确认文件存在。
2. 静态核对 `applicationId`、`versionCode`、签名证书一致性；不要因为 Gradle 构建成功就认定能覆盖升级。
3. 新 APK 覆盖安装，绝不要先卸载旧 APK，绝不要执行 `pm clear`、恢复出厂、清空 App 存储。
4. 升级后核对任务、项目、提醒事件、快捷键配置、电脑桥接配对是否保留；执行新记录添加、退出再进入、断网再进入。
5. 如需回滚：不要尝试降低 versionCode 直接覆盖；先从备份恢复数据，并考虑按 Android 平台约束处理安装版本。

## WebView / 作用域风险

- 保留旧版 WebView 数据目录与加载 origin。即使 APK 包名不变，若从 `file:///android_asset/...` 换为 `https://...` 或启用隔离数据目录，也可能看不到旧存储。
- 清空 WebView cache 与清空 WebView app data **不是一回事**。不允许用 `WebStorage.getInstance().deleteAllData()`、`clearData()` 清理所谓“缓存”。
- 直接在 WebView 中点击 Blob 下载不保证系统会保存。必须在 V9 真机核验导出机制，必要时接入已有原生 SAF 文件保存接口。
- 本模块本地快照与主数据同属应用存储；卸载或清空应用数据会同时删除。可靠恢复需要**外部**备份文件。
