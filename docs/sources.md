# 固定输入与实现依据

| 输入 | 固定点与用途 |
| --- | --- |
| [Hecker Floral](https://github.com/its-hecker/floral-motionsense-plugin/tree/92d0051faf53acac3dfefec6597a12d587eefa73) | `92d0051faf53acac3dfefec6597a12d587eefa73`，Settings、UI、动画和上游署名 |
| [Oslo APK](https://github.com/its-hecker/infinity_cnb_proprietary_vendor_google_coral/blob/211e454a5809b98fb85e883ace545fbdb9ba939d/proprietary/system_ext/priv-app/OsloFeedback/OsloFeedback.apk) | `211e454a5809b98fb85e883ace545fbdb9ba939d`，实际运行输入 |
| [Oslo 源码](https://github.com/its-hecker/infinity_OsloFeedback/tree/6dd8d1f3b99d9c2285defc0ddf5970043597504f) | `6dd8d1f3b99d9c2285defc0ddf5970043597504f`，服务、Clock 与用户参数调用依据 |
| [LOS framework](https://github.com/LineageOS/android_frameworks_base/tree/afcd876af2157908814f87383678b2bd4fb6b9b6) | `afcd876af2157908814f87383678b2bd4fb6b9b6`，SystemUI、framework 方法和 SettingsLib |
| [LOS 设备树](https://github.com/LineageOS/android_device_google_coral/tree/54913ec2b6e46e9d8d09ae21a15a3d1f7ca634dc) | `54913ec2b6e46e9d8d09ae21a15a3d1f7ca634dc`，flame/coral 共享平台及 oslo_app |
| [Nova 启动流程](https://github.com/SukiSU-Nova/SukiSU-Nova/blob/c60f21b9e00e35e898f8d21e0612465b76b9beec/userspace/ksud/src/init_event.rs) | `c60f21b9e00e35e898f8d21e0612465b76b9beec`，post-fs-data → system.prop → metamodule mount |
| [Nova 模块生命周期](https://github.com/SukiSU-Nova/SukiSU-Nova/blob/c60f21b9e00e35e898f8d21e0612465b76b9beec/userspace/ksud/src/module.rs) | 卸载脚本在下一次 post-fs-data 执行，因此适配 APK 的卸载安排为单次启动清理 |

Oslo 输入 SHA256：`5f6c2e0c908e4d726eb62543c8d7f8492ade99b1d9043baa415873093598ac54`。实际 APK 包含上游 Air DJ Java 构建内容；其关键权限检查和媒体、Clock 入口已与上述源代码核对。打包器逐项比较原 APK 的非签名 ZIP 内容，保证保留其 DEX、资源和清单。

Clock knownSigner 摘要来自已批准执行方案中的冻结 NikGapps Basic 检查：`f0fd6c5b410f25cb25c3b53346c8972fae30f8ee7411df910480ad6b2d60db83`。Settings 声明缺失的 `com.android.systemui.permission.SEND_ALERT_BROADCASTS`，保留 Oslo 原接收门槛；实际手机上的权限归属和授权留待验证。

1.0 再次核对 [NikGapps 的 Google Clock 8.7 单包](https://gitlab.com/api/v4/projects/85036487/packages/generic/nikgapps-google_clock/76060331-182f7c7b3787/google_clock.zip)（ZIP SHA256：`465c8a5553c8c996ea9d9809505e1af76ad61c5aef739d7ed406adc711e2007e`）。APK 版本为 `8.7 (881990392)`，证书与上述摘要一致；已导出的 `HandleApiCalls` 接收 `SNOOZE_ALARM` 和 `DISMISS_TIMER`，无需新增 `SET_ALARM` 请求。Clock 请求 SEND 权限并声明 `signatureOrSystem` 级别的 RECEIVE 权限，与本模块的正常授权路径匹配。该 APK 仅用于核对，不纳入模块或构建输入。

## 与执行方案对应的实现细节

项目使用一把固定签名密钥，mac XML 中以 `<package name="com.google.oslo">` 限定 `platform`，Settings 和适配 APK 使用普通独立 UID。XML 在每次启动时通过系统 Java XML API 解析、合并和复查；解析或标签设置失败时不挂载该文件。

Nova 调用 `uninstall.sh` 时 Android 服务尚未启动。0.2.0 采用极简卸载方案：仅在 `adapter.owned` 表明适配 APK 归属本模块时，将归属标记放入 `/data/adb/soli_motion-uninstall` 并登记 `/data/adb/service.d/soli_motion-cleanup.sh`；系统就绪后卸载该 APK，成功后删除任务与状态目录，失败则下次启动重试。安装和卸载均不读取、保存或恢复设置，`aware_*` 与系统共用的 `doze_*` 当前值保留。日常运行没有 `service.sh`、巡检守护进程或在线 `update.json`。

`ro.vendor.aware_available` 对应的 `system.prop` 仅由 `post-fs-data.sh` 每次开机生成，执行位置早于 Nova 加载属性与模块挂载。

Settings、SettingsLib 和编译桩的独立构建差异、依赖版本另见 [settings/UPSTREAM.md](../settings/UPSTREAM.md)。

## 安装与身份合并的审查依据

1.1 的挂载前置检查读取当前 ROM 的 vendor 规则，字段依据 [冻结 coral seapp_contexts](https://github.com/LineageOS/android_device_google_coral/blob/54913ec2b6e46e9d8d09ae21a15a3d1f7ca634dc/sepolicy/vendor/google/seapp_contexts)。[Android 17 seapp_contexts](https://android.googlesource.com/platform/system/sepolicy/+/android17-release/private/seapp_contexts) 将 target SDK ≤ 36 的 priv-app 分配至 `priv_app_36`；Oslo 的目标 SDK 为 28，失去专属规则后对应的通用 platform 域是 `platform_app_36`。

[冻结 LOS InstallPackageHelper](https://github.com/LineageOS/android_frameworks_base/blob/afcd876af2157908814f87383678b2bd4fb6b9b6/services/core/java/com/android/server/pm/InstallPackageHelper.java) 的 `scanPackageForInitLI` 支持同证书、更高版本的新系统包接管旧数据包并保留数据。[LSPosedService](https://github.com/LSPosed/LSPosed/blob/df74d83eb03a44cc6ad268841ac2ada28d077c77/daemon/src/main/java/org/lsposed/lspd/service/LSPosedService.java) 将完整卸载事件交给 [ConfigManager.removeModule](https://github.com/LSPosed/LSPosed/blob/df74d83eb03a44cc6ad268841ac2ada28d077c77/daemon/src/main/java/org/lsposed/lspd/service/ConfigManager.java)，后者删除模块记录与偏好。因此未来系统挂载迁移应验证无需先卸载的数据保留路径。

[冻结 SELinuxMMAC](https://github.com/LineageOS/android_frameworks_base/blob/afcd876af2157908814f87383678b2bd4fb6b9b6/services/core/java/com/android/server/pm/SELinuxMMAC.java) 使用 XML 解析后的属性值，并在 `ignoreMacPermissionsPackage()` 启用时跳过 package 子项；[开关定义](https://github.com/LineageOS/android_frameworks_base/blob/afcd876af2157908814f87383678b2bd4fb6b9b6/core/java/android/content/pm/flags.aconfig) 是大版本复核依据，本轮未测定设备最终开关状态。

Clock 的 Context 来源见 [OsloService.onCreate](https://github.com/its-hecker/infinity_OsloFeedback/blob/6dd8d1f3b99d9c2285defc0ddf5970043597504f/smali/classes/com/google/oslo/service/OsloService.smali) 与 [OsloBuiltInActions](https://github.com/its-hecker/infinity_OsloFeedback/blob/6dd8d1f3b99d9c2285defc0ddf5970043597504f/smali/classes/com/google/oslo/service/OsloBuiltInActions.smali)：传入的 Service 本身继承 ContextWrapper，现有 Clock Hook 覆盖实际调用链。
