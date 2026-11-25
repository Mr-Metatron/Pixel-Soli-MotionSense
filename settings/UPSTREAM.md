# Settings 的来源与独立构建改动

## 固定来源

| 内容 | 固定来源 |
| --- | --- |
| Motion Sense 页面、QS、Motion Lab、Air DJ、资源与测试 | [its-hecker/floral-motionsense-plugin，92d0051faf53acac3dfefec6597a12d587eefa73](https://github.com/its-hecker/floral-motionsense-plugin/tree/92d0051faf53acac3dfefec6597a12d587eefa73/settings) |
| SettingsLib UI 源码与资源 | [LineageOS/android_frameworks_base，afcd876af2157908814f87383678b2bd4fb6b9b6](https://github.com/LineageOS/android_frameworks_base/tree/afcd876af2157908814f87383678b2bd4fb6b9b6/packages/SettingsLib) |
| 上游共用设置资源 | [LineageOS/android_packages_resources_devicesettings，661fc4036da370a73e56dbd2949c18f8ab464b9b](https://github.com/LineageOS/android_packages_resources_devicesettings/tree/661fc4036da370a73e56dbd2949c18f8ab464b9b)；通过 Hecker 的 `settings/common-res` 原样引入 |
| 编译期隐藏 API 声明 | 同一固定 framework 的 `SystemProperties`、`DeviceConfig`、`AmbientDisplayConfiguration`；声明见根目录 `stubs/`，使用 `compileOnly`，运行实现由 ROM 提供 |

源码保留其 Apache-2.0 版权头；原 Pixel 动画沿用上游来源与权利说明，Motion Lab 动画来自 Hecker。许可证与总署名见仓库根目录。

## SettingsLib 范围

`settingslib/` 纳入 SettingsTheme、CollapsingToolbarBaseActivity、IllustrationPreference、FooterPreference、MainSwitchPreference、AppPreference、TopIntroPreference、TwoTargetPreference、Color 中实际使用的 UI 类与资源，以及 `PrimarySwitchPreference`。未引入 SettingsLib 的蓝牙、Wi-Fi、设备策略、数据库等业务模块。

为独立 Gradle 构建，将各 Soong 资源包的 `R` 引用归并为 `com.android.settingslib.R`；`values` XML 文件名前缀用于避免文件名冲突，资源名称与内容保持不变。AndroidX Preference 固定为 1.2.1，Fragment 为 1.8.6，Activity 为 1.10.1，Core 为 1.15.0，ConstraintLayout 为 2.2.1，Material 为 1.14.0，Lottie 为上游采用的 5.2.0。Material 1.14.0 提供本版 SettingsLib 使用的 Expressive 样式。

Soong 的两个生成式功能开关以本地 `Flags` 类提供：Expressive 界面和空 Lottie 隐藏均启用。原有 SDK 条件、日夜主题、系统配色和用户手势设置逻辑继续生效。私有 headline 字体资源使用 `sans-serif`；私有系统对话框主题改为这份 SettingsLib 自带的同名日夜主题。

`PrimarySwitchPreference` 使用原有 `TwoTargetPreference` 基类和开关控件，移除本应用从未调用的设备管理员入口与系统 JankMonitor 接入。这些依赖原本由完整 ROM Settings 工程提供；切换、点击进入子页面和状态更新保留原实现。

## Settings 应用改动

包名保持 `org.hecker.floral.motionsense`。移除 `android.uid.system` 与无需使用的 persistent 启动方式，加入 `usesNonSdkApi`、`READ_DEVICE_CONFIG`，保留 `WRITE_SECURE_SETTINGS`。Lab 使用已有 OsloService Binder 接口，由适配 APK 针对本包和项目证书授权，因此删除无法由项目签名获得的 `STATUS_BAR_SERVICE` 请求。

增加 Launcher 查询声明，使独立 UID 下的媒体应用选择器可列出普通已安装应用。资源引用只改为合并后的 SettingsLib namespace；`UserHandle.myUserId()` 换为平台 UID 分解规则 `Process.myUid() / 100000`，其余 Settings 业务源码保持上游实现。

主页面保留上游 `IA_SETTINGS` 系统设置入口，并新增 `MAIN` / `LAUNCHER` 应用抽屉入口，便于安装独立模块后直接打开 Motion Sense。

Clock 的发送权限名称为 `com.android.systemui.permission.SEND_ALERT_BROADCASTS`，与固定 Oslo 接收器一致；按执行方案在 Settings 清单声明 `signature|knownSigner`，Google Clock 证书 SHA-256 位于 `res/values/clock_signers.xml`。该声明对应冻结 LOS 缺少权限定义的路径。

## Doze RRO

根目录 `doze-overlay/` 仅覆盖 `android:bool/config_dozeWakeLockScreenSensorAvailable=true`。固定 framework 中默认值为 false，且 framework 资源没有 overlayable 分组；预装到 system_ext 后按现有分区策略处理，无 `targetName`。用户的 Doze、常亮、节电设置仍由 ROM 与原有 Settings 代码处理。

## 验证

上游共用资源的四个旧翻译文件保留了没有默认语言条目的 `switch_bar_on`、`switch_bar_off`、`doze_settings_help_title`、`doze_settings_help_text`。已核对 Settings 业务源码、布局和这份 SettingsLib 均没有引用，也没有按名称动态查找这些资源；`lint.xml` 仅忽略这四个原始文件的 `ExtraTranslation`，保留翻译文件与其他 lint 检查。

`settings/tests/LabEngineTest.java` 与六组 Lottie 资产测试来自上游。独立构建应同时完成 APK 的资源链接、Java/Kotlin 编译和 DEX 生成。Settings 页面、QS、Lab 事件、Air DJ 媒体动作、Clock 和 Doze 的实际运行结果须在 Pixel 4 上验证。
