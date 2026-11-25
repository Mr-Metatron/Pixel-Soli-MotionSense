# LSPosed 适配层

入口为 `SoliEntry.handleLoadPackage`，仅处理 `com.android.systemui` 与 `com.google.oslo` 的主进程，在 Application 初始化之前安装 Hook。建议作用域也只包含这两个包。

## 功能边界

| 所在进程 | 入口 | 改动 |
| --- | --- | --- |
| SystemUI | `Resources.getStringArray(int)` | 按完整资源名识别 `config_pluginAllowlist`，追加 `com.google.oslo`，保留原数组内容与顺序 |
| SystemUI | `ApplicationPackageManager.checkPermission(String,String)` | 仅对本项目签名的 Oslo 请求 `com.android.systemui.permission.PLUGIN` 返回 granted |
| Oslo | `OsloService.checkPermission()` | 本进程 UID、实际 UID 与项目证书都匹配的 Settings 可通过；其他调用执行原检查 |
| Oslo | 媒体查询与监听 | 将 `UserHandle.ALL`、`CURRENT` 改为 `Process.myUserHandle()` |
| Oslo | Clock 接收器与操作 | 仅对原 `SEND_ALERT_BROADCASTS` 接收器和 `SNOOZE_ALARM` / `DISMISS_TIMER` 操作改写特殊用户参数 |
| Oslo | `Settings.Secure.getIntForUser` | 仅处理方案中的五个 Motion Sense 设置键 |

两个插件的日志通过只读观察 `PluginInstance.onCreate()` 与 `loadPlugin()` 产生。插件版本检查、启用状态、实例创建与失败保护继续由 SystemUI 处理。

证书摘要由根工程的 `soliCertSha256` 写入 BuildConfig。SystemUI 按方案缓存本次进程的证书核对结果，因此安装或升级整个模块后需完整重启。Oslo 的 Settings 调用检查每次重新读取 UID 与签名，避免包卸载重装后复用旧 UID 的缓存授权。Binder 身份始终保持原值。

## 固定来源

方法签名依据 [LineageOS framework afcd876](https://github.com/LineageOS/android_frameworks_base/tree/afcd876af2157908814f87383678b2bd4fb6b9b6) 与 [Oslo 源码 6dd8d1f](https://github.com/its-hecker/infinity_OsloFeedback/tree/6dd8d1f3b99d9c2285defc0ddf5970043597504f)，并对构建输入中的实际 Oslo APK 核对。

`ScopePolicyTest` 覆盖允许与拒绝边界，包括进程筛选、数组保留、错误证书、共享 UID、显式用户 ID、非业务设置键与无关 Clock 操作。完整构建时运行 `./gradlew :adapter:testReleaseUnitTest`。手机端 Hook 命中、插件加载与手势效果仍需实机验证。
