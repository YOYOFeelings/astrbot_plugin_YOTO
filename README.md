<div align="center">

![:name](https://count.getloli.com/@astrbot_plugin_YOTO?name=astrbot_plugin_YOTO&theme=miku&padding=7&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

# astrbot_plugin_YOTO

_✨ 多功能 QQ 群管理插件 ✨_  

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-4.0%2B-orange.svg)](https://github.com/Soulter/AstrBot)
[![GitHub](https://img.shields.io/badge/作者-感情-blue)](https://qm.qq.com/q/jpk9DM9Zo4)

</div>

## 📦 安装

在 AstrBot 的插件市场搜索 `astrbot_plugin_YOTO`，点击安装即可。  
或手动克隆仓库到 `data/plugins` 目录。

## ⚙️ 功能介绍

本插件提供群管、签到、积分、排行榜、每日一言、视频解析、刷屏检测等功能，所有功能均可在配置面板中灵活开关和自定义。

### 核心功能

| 功能模块 | 说明 |
|---------|------|
| **管理员设置** | 设置管理员QQ号列表、群白名单控制（白名单为空时所有群均无法使用，需显式填写） |
| **群管功能** | 全员禁言、禁言/解禁、踢人、拉黑、撤回消息、宵禁定时任务 |
| **签到系统** | 支持24小时制/日期制，固定或随机积分，连续签到奖励 |
| **排行榜** | 积分榜、签到榜（已移除使用榜） |
| **每日一言** | 支持固定文本或一言API |
| **视频解析** | 调用外部 API 解析抖音、快手、B站等平台视频，自动下载图片/视频并发送；<br>若视频超过 50MB 自动压缩为 ZIP 文件发送；若 ZIP 文件超过 100MB，则放弃发送文件，仅提供原始链接 |
| **刷屏检测** | 自动检测刷屏行为并禁言 |
| **显示设置** | 菜单/签到/排行榜/个人信息支持图片/文字模式，可自定义背景、字体、颜色、模糊效果；菜单标题和底部文本完美居中 |
| **自定义提示语** | 支持自定义禁言自己时的随机语录 |

## ⌨️ 命令列表

| 命令 | 说明 |
|------|------|
| `菜单` | 查看功能菜单（支持图片/文字两种显示方式） |
| `管理员菜单` | 查看管理员功能菜单（仅管理员可见） |
| `个人信息` / `个人信息 @用户` | 查看自己或指定用户的积分、签到次数、排名等信息（已移除商品购买记录） |
| `签到` | 每日签到获取积分 |
| `积分` | 查看当前积分 |
| `积分榜` | 显示积分排行榜 |
| `签到榜` | 显示签到天数排行榜 |
| `解析 <链接>` | 解析视频/图文链接，自动下载并发送（视频超50MB自动压缩为ZIP） |
| `禁言 <@用户/QQ号> [秒数]` | 禁言指定成员（默认600秒） |
| `禁我 [秒数]` | 禁言自己 |
| `解禁 <@用户/QQ号>` | 解除禁言 |
| `全员禁言` / `关闭全员禁言` | 控制全群发言权限 |
| `踢人 <@用户/QQ号>` | 将成员踢出群聊 |
| `拉黑 <@用户/QQ号>` | 踢出并拉黑成员 |
| `撤回 [数量]` | 撤回消息：可引用消息撤回单条，或 @用户并指定数量撤回其最近消息 |
| `开启宵禁 [HH:MM HH:MM]` | 开启宵禁（定时全员禁言），留空使用默认时间 |
| `关闭宵禁` | 关闭本群宵禁任务 |

*注：命令前缀可在配置中设置，留空则直接匹配。*

## 🔧 配置说明

进入插件配置面板进行详细配置，主要配置项如下：

### 管理员设置 (admin)
- **admin_qq**：管理员QQ号列表，例如 `["10001", "10002"]`（留空则无管理员权限）
- **group_whitelist**：允许使用插件的QQ群白名单，**空列表表示所有群都禁止使用**，需显式填写允许的群号

### 功能开关 (features)
- **enable_mute_all**：全员禁言功能开关
- **enable_ban**：禁言/解禁功能开关
- **enable_kick**：踢人功能开关
- **enable_block**：拉黑功能开关
- **enable_recall**：撤回功能开关
- **recall_max_count**：单次最多撤回的消息条数（默认10）

### 视频解析 (video_parse)
- **enable_video_parse**：开启视频解析功能
- **api_base**：解析API基础地址（固定为 `https://api.bugpk.com/api`，不可修改）
- **video_send_mode**：发送方式，可选“分开发送”或“合并转发”
- **max_concurrent_downloads**：（已弃用）原用于控制并发下载数，当前固定为顺序下载

### 宵禁设置 (curfew)
- **enable**：开启宵禁功能（定时全员禁言）
- **default_start**：默认开始时间，如 `23:00`
- **default_end**：默认结束时间，如 `06:00`

### 显示设置 (display)
- **menu_style / sign_style / rank_style / profile_style**：菜单/签到/排行榜/个人信息显示方式（图片或文字）
- **profile_blur_radius / rank_blur_radius / menu_blur_radius**：背景图模糊半径（0-5）
- **title_color / text_color**：标题和正文颜色（十六进制）
- **background_image / font_file**：背景图和字体文件名（需放在 `assets` 目录）
- **menu_title**：菜单顶部标题
- **menu_extra_center**：菜单底部居中文本

### 签到设置 (sign)
- **enable_sign**：签到功能开关
- **sign_mode**：签到模式（24小时制/日期制）
- **points_type**：积分获得方式（固定值/范围随机）
- **fixed_points / random_min / random_max**：积分值设置
- **continuous_bonus**：连续签到额外奖励天数列表（逗号分隔）

### 刷屏检测 (spam)
- **enable_spam_detect**：刷屏检测开关
- **spam_count**：检测消息数量（3-10条）
- **spam_interval**：检测时间间隔（0.1-2.0秒）
- **spam_ban_time**：刷屏禁言时长（秒，0关闭）

### 排行榜设置 (rank)
- **enable_rank**：排行榜功能开关
- **points_rank_title / sign_rank_title**：积分榜/签到榜标题
- **rank_max_lines**：排行榜显示人数（5-30）

### 每日一言 (daily_quote)
- **quote_source**：一言来源（固定文本/一言API）
- **fixed_quote**：固定一言内容
- **api_url / api_json_path**：API地址和JSON字段路径

### 命令与消息 (command / messages)
- **command_prefix**：群内命令前缀（留空直接匹配）
- **ban_me_quotes**：禁言自己时的随机语录（每行一条）

## 📌 注意事项

- 若群白名单为空列表，**所有群均无法使用插件**，请务必填写允许的群号。
- 视频解析功能依赖于外部 API，如遇解析失败请检查网络或稍后重试。
- 超过 50MB 的视频会被自动压缩为 ZIP 文件发送；若 ZIP 文件超过 100MB，则放弃发送文件，仅提供原始链接。
- 宵禁任务会持久化保存，重启 Bot 后自动恢复。
- 如需修改背景图片或字体文件，请将文件放入 `assets` 目录，并在配置中填写文件名。

## 🤝 支持与反馈

如有问题或建议，欢迎联系作者：[点击添加QQ](https://qm.qq.com/q/jpk9DM9Zo4)
