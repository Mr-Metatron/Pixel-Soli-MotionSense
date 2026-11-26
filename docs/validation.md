# 构建验证与实机状态

本页区分可由源码和自动构建验证的实现，以及在 Pixel 4（flame，LineageOS `24.0-20261119-NIGHTLY`，SukiSU Nova `v3.0.0`，Magic Mount-rs `v4.1.12`，NyaZygisk `v2.6`，LSPosed `v2.2.1`）上的实机验证记录。

## 0.2.4 的交付范围

以 `d4de87c` 的已有功能和实机修复为基线，核对执行方案中的核心与扩展功能。SystemUI 和 Oslo 的 Hook 重载、Lab Binder 协议、普通来电权限以及 Nova 启动顺序均与固定上游源码匹配。Settings、QS、训练、Glow Studio、Air DJ、Clock 和 Doze 已包含在工程中。

本版补上 Motion Lab 原生 Activity 对系统栏与屏幕切口的适配。下表中的实机结果来自截至 0.2.3 的已有记录；本次没有新增手机操作或硬件验收结果，界面修复也需在设备上观察。对应源码和自动构建结果以 [Actions](https://github.com/Mr-Metatron/Pixel-Soli-MotionSense/actions/workflows/build.yml) 为准。

## 自动检查覆盖

构建流程会编译三个项目 APK、重签固定 Oslo，核对四个 APK 的项目证书及包名。打包检查验证系统分区路径、模块 ID、运行时无隐藏 API/Xposed 编译桩、Oslo 非签名内容保持原样，以及每次启动动态生成 mac 身份文件。

Hook 单元测试覆盖错误签名、系统应用与更新标志、其他包/权限、共享 UID、显式用户 ID、无关设置键和 Clock action 的原行为。XML 合并测试覆盖保留原条目、包名限定、重复执行、损坏 XML、DTD、冲突身份和误用 SHA256 摘要。安装生命周期测试使用隔离的模拟 Android 命令，覆盖 APK 归属继承、独立安装包保留、卸载后重装、旧状态迁移、失败重试和设置值保持。上游 LabEngine 与 Lottie 资产测试也包含在构建中。

具体通过记录以 [Actions](https://github.com/Mr-Metatron/Pixel-Soli-MotionSense/actions/workflows/build.yml) 的对应提交为准，包内 `build-info.json` 保存源码提交、证书和 APK 摘要。

## 待实机确认

| 项目 | 当前状态 | 观察结果 |
| --- | --- | --- |
| 模块安装、APK 自动升级 | 实机通过 | 需先装 Magic Mount-rs；适配包自动安装并显示于 LSPosed |
| Oslo 身份和正常权限 | 实机通过 | system_ext priv-app、`oslo_app` 域、全局 `Enforcing`；`dalvikvm` 兼容 ART APEX 路径，`boot-completed.sh` 一次性补授 `RECORD_AUDIO` |
| SystemUI 两个插件 | 实机通过 | allowlist 与 PLUGIN Hook 命中，`OsloOverlay` 与 `OsloSensorManager` 均 `loaded` 并接入 `OsloService` |
| 媒体手势与 glow | 初步实机通过，待常规模式复测 | CHRE 7 端点在线、`mNanoAppFound: true`，实测抓到大量 `Flick`/`Tap`/`Reach` 事件；此前开启了 Air DJ 接管为音量/切档，关闭 Air DJ 后的常规切歌/暂停与 glow 待复测 |
| Settings、QS、Motion Lab、Air DJ | Settings / Air DJ 已实机启动，其余待复测 | 补 `priv_app_36` 读取 `vendor_aware_available_prop` 规则后可正常读取可用性；非支持地区（如 `cn`）需临时 `pixel.oslo.allowed_override=1` 验证；Air DJ 切档与音量动作已触发 |
| Clock、普通来电 | 已实现兼容路径，待实机验证 | 闹钟贪睡、计时器停止、来电静音与音量恢复 |
| Doze 与伸手接近 | RRO 已启用，行为待实机验证 | `[x] org.metatron.soli.overlay.doze` 已启用，灭屏伸手亮屏待实测 |
| 3D 人脸 | 原实现保留，待回归验证 | 普通解锁正常，记录接近时认证启动顺序 |
| 停用、卸载、设置保留 | 已实现，待实机验证 | 重启后模块撤回，`aware_*` 与 `doze_*` 当前值保留，仅移除归属本模块的适配 APK，一次性任务自删 |
| 官方 OTA | 已实现动态配置合并，待有 OTA 时验证 | 新槽位 Root 可用后，插件、手势、设置、人脸正常 |

## 最小定位命令

```sh
adb shell getprop ro.product.device
adb shell getprop ro.lineage.version
adb shell getprop ro.vendor.aware_available
adb shell su -c 'cat /sys/fs/selinux/enforce'
adb shell dumpsys package com.google.oslo
adb shell dumpsys package org.hecker.floral.motionsense
adb shell ps -AZ
adb shell dumpsys contexthub
adb shell dumpsys media_session
adb shell cmd overlay list
```

先看 LSPosed 中 `SoliMotion` 日志和模块 `state/identity.log`。确有权限错误时再收集对应时段 logcat/AVC；只按具体拒绝补充策略。当前 `sepolicy.rule` 仅包含 Android 17 `priv_app_36` 读取 `vendor_aware_available_prop` 的单条规则。

## 已知范围

首版面向主用户。旧 Google Call Screen 增强协议、MotionSenseBridge 和多用户扩展尚未接入。SystemUI 经 ART 优化后两个 Hook 是否持续命中，需要实际设备验证；当前未加入全局去优化。Google Clock 更新后的授权和广播行为按实际版本复核。
