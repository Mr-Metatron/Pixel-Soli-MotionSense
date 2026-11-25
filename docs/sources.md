# 固定输入与实现依据

| 输入 | 固定点与用途 |
| --- | --- |
| [Hecker Floral](https://github.com/its-hecker/floral-motionsense-plugin/tree/92d0051faf53acac3dfefec6597a12d587eefa73) | `92d0051faf53acac3dfefec6597a12d587eefa73`，Settings、UI、动画和上游署名 |
| [Oslo APK](https://github.com/its-hecker/infinity_cnb_proprietary_vendor_google_coral/blob/211e454a5809b98fb85e883ace545fbdb9ba939d/proprietary/system_ext/priv-app/OsloFeedback/OsloFeedback.apk) | `211e454a5809b98fb85e883ace545fbdb9ba939d`，实际运行输入 |
| [Oslo 源码](https://github.com/its-hecker/infinity_OsloFeedback/tree/6dd8d1f3b99d9c2285defc0ddf5970043597504f) | `6dd8d1f3b99d9c2285defc0ddf5970043597504f`，服务、Clock 与用户参数调用依据 |
| [LOS framework](https://github.com/LineageOS/android_frameworks_base/tree/afcd876af2157908814f87383678b2bd4fb6b9b6) | `afcd876af2157908814f87383678b2bd4fb6b9b6`，SystemUI、framework 方法和 SettingsLib |
| [LOS 设备树](https://github.com/LineageOS/android_device_google_coral/tree/54913ec2b6e46e9d8d09ae21a15a3d1f7ca634dc) | `54913ec2b6e46e9d8d09ae21a15a3d1f7ca634dc`，flame/coral 共享平台及 oslo_app |
| [Nova 启动流程](https://github.com/SukiSU-Nova/SukiSU-Nova/blob/c60f21b9e00e35e898f8d21e0612465b76b9beec/userspace/ksud/src/init_event.rs) | `c60f21b9e00e35e898f8d21e0612465b76b9beec`，post-fs-data → system.prop → metamodule mount |
| [Nova 模块生命周期](https://github.com/SukiSU-Nova/SukiSU-Nova/blob/c60f21b9e00e35e898f8d21e0612465b76b9beec/userspace/ksud/src/module.rs) | 卸载脚本在下一次 post-fs-data 执行，因此恢复设置安排为单次启动清理 |

Oslo 输入 SHA256：`5f6c2e0c908e4d726eb62543c8d7f8492ade99b1d9043baa415873093598ac54`。实际 APK 包含上游 Air DJ Java 构建内容；其关键权限检查和媒体、Clock 入口已与上述源代码核对。打包器逐项比较原 APK 的非签名 ZIP 内容，保证保留其 DEX、资源和清单。

Clock knownSigner 摘要来自已批准执行方案中的冻结 NikGapps Basic 检查：`f0fd6c5b410f25cb25c3b53346c8972fae30f8ee7411df910480ad6b2d60db83`。Settings 声明缺失的 `com.android.systemui.permission.SEND_ALERT_BROADCASTS`，保留 Oslo 原接收门槛；实际手机上的权限归属和授权留待验证。

## 与执行方案对应的实现细节

项目使用一把固定签名密钥，mac XML 中以 `<package name="com.google.oslo">` 限定 `platform`，Settings 和适配 APK 使用普通独立 UID。XML 在每次启动时通过系统 Java XML API 解析、合并和复查；解析或标签设置失败时不挂载该文件。

卸载阶段存在真实时序差异：Nova 调用 uninstall.sh 时 Android 服务尚未启动。实现将项目快照复制到 `/data/adb/soli_motion-uninstall`，登记 `/data/adb/service.d/soli_motion-cleanup.sh`；系统就绪后恢复、卸载归属本模块的适配 APK，再删除任务和快照。失败时保留快照供下次启动重试。日常运行没有 service.sh、巡检守护进程或在线 update.json。

Settings、SettingsLib 和编译桩的独立构建差异、依赖版本另见 [settings/UPSTREAM.md](../settings/UPSTREAM.md)。
