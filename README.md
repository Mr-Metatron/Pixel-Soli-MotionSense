# Pixel Soli Motion Sense

为 Pixel 4（flame，兼容同平台 coral）和 LineageOS 24 准备的 Motion Sense 模块。一个 ZIP 内包含 Oslo、Hecker 原版 Settings、LSPosed 适配 APK 和 Doze RRO。

**当前为开发版本，硬件功能待实机验证。** 构建和包检查会验证签名、APK 布局、Hook 边界、设置恢复、上游内容及编译桩排除；雷达手势、动画、人脸和 OTA 的结果记录在 [验证说明](docs/validation.md)。

## 下载与安装

从 [GitHub Releases](https://github.com/Mr-Metatron/Pixel-Soli-MotionSense/releases) 下载 `soli_motion-<版本>.zip`。开发构建位于 [Actions](https://github.com/Mr-Metatron/Pixel-Soli-MotionSense/actions/workflows/build.yml) 中每次成功运行的 Artifacts；解开下载的 Artifacts 外层压缩包后，刷入其中的模块 ZIP。

运行环境为已有的 SukiSU Nova、Magic Mount-rs、独立 NyaZygisk 和 LSPosed。Nova 内置 Zygisk 保持关闭，SystemUI、Oslo 和 Motion Sense Settings 允许业务挂载；LSPosed 注入只选择前两个包。

- 在 Nova 管理器安装模块 ZIP。安装器自动安装或升级内置的 LSPosed 适配 APK。
- 在 LSPosed 中启用 **Soli Motion Sense Adapter**，只勾选 **SystemUI（com.android.systemui）** 和 **Oslo（com.google.oslo）**。
- 完整重启，打开应用抽屉中的 **Motion Sense**，启用所需手势。地区、飞行模式、省电和用户的 Doze 开关沿用上游状态机。

首次刷入前可保存 `ro.product.device`、`ro.lineage.version` 和 `/sys/fs/selinux/enforce` 的当前值。新增模块后的全局 SELinux 应继续为 Enforcing。现有可用的框架版本可继续使用。

## 更新与卸载

升级时刷入同一项目签名的新 ZIP，再完整重启。模块 ID 固定为 `soli_motion`。每次启动从当前 ROM 合并 Oslo 的签名身份映射，普通 OTA 后继续使用新的 ROM 配置。

正常卸载前关闭 Motion Sense，在 Nova 中移除模块并重启。Nova 在早期启动阶段执行卸载脚本；本模块会把原设置快照交给一次性启动清理，系统就绪后恢复并自删。适配 APK 由本模块首次安装时，也会一并移除；用户事先独立安装的适配包保留。独立 Nya、Magic Mount-rs 和 LSPosed 框架继续保留。

遇到 SystemUI 连续崩溃，可通过已可用的 ADB Root 停用模块：

```sh
adb shell su -c 'touch /data/adb/modules/soli_motion/disable'
adb reboot
```

ADB 不可用时使用 Nova 原有安全模式。停用后需要完整重启，才能结束旧插件进程和挂载。

## 实现范围

| 组件 | 本项目的改动 |
| --- | --- |
| Oslo | 固定上游 APK，保持 DEX、资源和 manifest，仅重签并系统化部署 |
| SystemUI 适配 | 按资源名合并插件白名单，只对本项目签名的 Oslo 通过本地 PLUGIN 检查 |
| Oslo 适配 | 允许自身与同项目签名的 Settings 调用；仅把所需 ALL/CURRENT 用户参数改为本用户 |
| Settings | 复用 Hecker UI、QS、Motion Lab、Air DJ；独立构建，移除共享 system UID，补显式权限 |
| SELinux | 当前 ROM 的 mac 文件增加仅限 com.google.oslo 的 signer 映射，复用已有 oslo_app |
| Doze | RRO 仅启用 config_dozeWakeLockScreenSensorAvailable |

工程保持现有内核、SystemUI APK、CHRE/固件及人脸实现。Hook 方法和限制见 [adapter 说明](adapter/README.md)，Settings 的最小构建改动见 [上游记录](settings/UPSTREAM.md)。

## 自动构建

唯一工作流为 [build.yml](.github/workflows/build.yml)。每次 push 或手动运行自动测试、构建、统一签名并上传一个模块 ZIP；推送与 `soliVersionName` 一致的 `v*` 标签，或手动勾选 `release`，会创建 GitHub 预发布并附上 ZIP 与 SHA256。也可在 `main` 的提交消息中加入 `[release]` 明确触发发版，便于直接通过 GitHub 连接器完成交付。

工具版本固定为 JDK 17.0.17+10、Gradle 8.11.1、AGP 8.9.3、Android SDK 36、Build Tools 35.0.0。下载的唯一外部应用输入为 Oslo，固定地址和 SHA256 直接写在 [构建脚本](scripts/build.sh)。

仓库附带固定项目开发签名，开箱即可构建。可选的单一 Secret `SOLI_SIGNING_KEY` 使用 PKCS12 文件的 Base64，alias 为 `soli`、密码为 `soli_motion`。该覆盖同时用于所有 APK、Hook 证书校验和 Oslo 身份映射。安装后的更新需要保持签名一致。

本地构建用于开发调试：

```sh
sdkmanager 'platforms;android-36' 'build-tools;35.0.0'
bash scripts/build.sh
```

输出为 `dist/soli_motion-0.1.0.zip`。公开交付使用云端构建，用户无需安装 SDK。

## 调试与来源

优先检查 LSPosed 内本项目日志；身份合并日志在 `/data/adb/modules/soli_motion/state/identity.log`。具体检查命令和待验证功能见 [验证说明](docs/validation.md)。

本项目按 [执行方案](https://docs.google.com/document/d/1Cd-hJ8xmdrgYeIqemOTKAmHal8bernLzfqjb_ltqTCk) 实现；固定源码及 APK 来源见 [来源记录](docs/sources.md)。项目代码采用 Apache-2.0，上游版权和预编译组件说明保留于 [NOTICE](NOTICE)。
