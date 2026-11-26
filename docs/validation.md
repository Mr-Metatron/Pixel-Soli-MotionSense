# 构建验证与实机状态

本页区分可由源码和自动构建验证的实现，以及在 Pixel 4（flame，LineageOS `24.0-20261119-NIGHTLY`，SukiSU Nova `v3.0.0`，Magic Mount-rs `v4.1.12`，NyaZygisk `v2.6`，LSPosed `v2.2.1`）上的实机验证记录。

## 当前交付：1.1

1.1 基于 `9eacf51` 修复代码审查确认的问题：固定发布签名校验、身份挂载前的 vendor 规则检查、每次启动的只读健康日志、SystemUI 资源 ID 缓存、删除 v0.1 迁移分支，以及发布入口和版本更新方式收敛。完整 Android 编译、签名和打包由 GitHub Actions runner 执行。

自动构建覆盖 8 项 Hook 边界单元测试、13 项身份 XML 合并检查、16 项生命周期测试、4 项发布签名预检测试、10 项 LabEngine 检查和 6 组动画资产检查。签名负向测试执行真实构建脚本的预检，确认缺失 Secret、错误证书及损坏的密钥输入会在下载或编译之前失败；正式构建则验证原有发布密钥可以通过。

本次没有新增手机操作。下表保留截至 0.2.3 的已有实机记录；1.0 的界面改动与 1.1 的开机检查、健康日志及升级行为仍需设备确认。

## 保留的完整功能

以 `d4de87c` 的已有功能和实机修复为基线，核对执行方案中的核心与扩展功能。SystemUI 和 Oslo 的 Hook 重载、Lab Binder 协议、普通来电权限以及 Nova 启动顺序均与固定上游源码匹配。Settings、QS、训练、Glow Studio、Air DJ、Clock 和 Doze 已包含在工程中。

1.0 已补上 Motion Lab 原生 Activity 对系统栏与屏幕切口的适配。对应源码和自动构建结果以 [Actions](https://github.com/Mr-Metatron/Pixel-Soli-MotionSense/actions/workflows/build.yml) 为准。

## 自动检查覆盖

构建流程会编译三个项目 APK、重签固定 Oslo，核对四个 APK 的项目证书及包名。打包检查验证系统分区路径、模块 ID、运行时无隐藏 API/Xposed 编译桩、Oslo 非签名内容保持原样，以及每次启动动态生成 mac 身份文件。

Hook 单元测试覆盖错误签名、系统应用与更新标志、其他包/权限、共享 UID、显式用户 ID、无关设置键和 Clock action 的原行为。XML 合并测试覆盖保留原条目、包名限定、重复执行、损坏 XML、DTD、冲突身份和误用 SHA256 摘要。生命周期测试使用隔离的模拟 Android 命令，覆盖 APK 归属继承、独立安装包保留、卸载后重装、失败重试、设置值保持、域规则变化和健康日志。上游 LabEngine 与 Lottie 资产测试也包含在构建中。

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

先读本次启动快照：

```sh
adb shell su -c 'cat /data/adb/modules/soli_motion/state/health.log'
```

`oslo_domain_rule=present` 表示 vendor 文件中保留了已知适用规则；`identity_file=matches_visible_file` 表示生成文件与系统当前可见文件相同；有 Oslo 进程时，`domain=expected` 表示其真实上下文为 `oslo_app`。`not_running` 表示采样时尚无进程，可在使用 Motion Sense 后查看 `ps -AZ`。出现缺失、不一致或 `unexpected` 时，查看同目录 `identity.log` 及对应组件日志。快照在每次启动完成时覆盖，权限为 `0600`，没有常驻巡检。

插件问题看 LSPosed 中 `SoliMotion` 日志。确有权限错误时再收集对应时段 logcat/AVC；只按具体拒绝补充策略。当前 `sepolicy.rule` 仅包含 Android 17 `priv_app_36` 读取 `vendor_aware_available_prop` 的单条规则，该域对应 target SDK ≤ 36。

## 审查中保留的实现

**适配 APK 的安装方式保持不变。** 系统挂载可以减少卸载脚本，但迁移应保留现有 LSPosed 启用和作用域。冻结 LOS 的包管理器允许同证书、更高 versionCode 的新系统包接管已有数据包并保留数据；先执行 `pm uninstall` 则会触发 LSPosed 删除模块配置。后续改造应验证这条无卸载迁移，以及停用、升级和移除行为，再删除现有安装链。相关源码见 [来源记录](sources.md#安装与身份合并的审查依据)。

**身份 XML 保留系统解析器。** 在真实根结束标签前插入固定片段可以保持已知合法 XML 的结构，但关闭标签计数、字面证书搜索和字节数检查没有覆盖解析后证书识别、重复项及已有身份冲突。当前实现保留 DER/X.509 检查、限定包名的合并、输出复查和原子替换；ART APEX 与 `/system/bin` 两条路径继续兼容，实际超时或失败会写入健康日志。

**Clock Hook 保留在 ContextWrapper。** 固定版 `OsloService` 把 Service 自身传入内置 Action，Clock 的接收器和 Activity 调用均经过现有方法；当前没有漏掉 `ContextImpl` 路径的源码证据。仍需按表中状态完成闹钟和计时器实测。

## OTA 与大版本复核

同一 Android 版本的普通 OTA 后，按 Nova 原有流程保留新槽位 Root；启动后查看健康日志，确认模块、插件和设置入口，再试一次媒体手势、glow 与人脸解锁。缺少 vendor 规则时本版会跳过身份挂载，日志给出具体原因。

QPR 或 Android 大版本升级时，再对照新 ROM 复核下列接口和实际行为：

| 检查层 | 复核内容 |
| --- | --- |
| 身份与 SELinux | 当前 ROM 的 mac 文件可解析；vendor Oslo 规则仍适用；实际进程为 `oslo_app`；精确属性规则中的类型仍存在 |
| framework 策略加载 | 仍接受 package 级 mac 映射。冻结源码已有 `ignore_mac_permissions_package` 开关，升级时核对其最终构建状态及真实进程域 |
| SystemUI | `config_pluginAllowlist` 可按资源名解析；本地 PLUGIN 校验仍命中；两个插件完成加载 |
| Oslo 用户参数 | 媒体查询、媒体监听、Clock 接收器、Clock Activity、Secure 设置读取五处重载和调用路径仍匹配 |
| Settings 与 Doze | 编译桩对应的隐藏 API 可用；Settings/QS/Lab 可打开；RRO 资源及 idmap 有效；伸手、人脸与省电行为正常 |
| 模块运行环境 | Nova 启动顺序、Magic Mount-rs、Nya 与 LSPosed 注入正常；卸载和停用后模块撤回 |

## 已知范围

首版面向主用户。旧 Google Call Screen 增强协议、MotionSenseBridge 和多用户扩展尚未接入。SystemUI 经 ART 优化后两个 Hook 是否持续命中，需要实际设备验证；当前未加入全局去优化。Google Clock 更新后的授权和广播行为按实际版本复核。
