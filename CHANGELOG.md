# 版本记录

## 0.2.4

修复独立 Settings APK 提高 target SDK 后的 Motion Lab 显示：训练页面与 Glow Studio 的滚动容器避开状态栏、导航栏和屏幕切口，保留上游页面、动画和交互。

本次公开发布同时包含此前 0.2.x 的安装与运行修复：Nova 中的流式 APK 安装、LOS 24 的 ART APEX `dalvikvm` 路径、Settings 读取雷达可用性属性、Oslo 首次启动的录音授权，以及保留用户设置的卸载流程。已有安装继续使用相同的模块 ID、包名和项目签名覆盖升级。

方案中的媒体手势、glow、Settings、QS、Motion Lab、Air DJ、Clock、普通来电和 Doze 都已纳入单一模块。实机状态沿用 [验证说明](docs/validation.md) 中的逐项记录；0.2.4 的界面修复和尚未完成的功能实测留待设备确认。
