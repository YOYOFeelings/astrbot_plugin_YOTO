import os
import asyncio
import random
import time
from pathlib import Path
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
from astrbot.core.star.filter.event_message_type import EventMessageType
from astrbot.core.message.components import Reply, Plain, Image, Video

# 尝试导入 MessageChain，优先从 api 导入
try:
    from astrbot.api.message import MessageChain
except ImportError:
    try:
        from astrbot.core.message.components import MessageChain
    except ImportError:
        MessageChain = None
        logger.warning("MessageChain 导入失败，视频解析将分开发送")

from .config import PluginConfig
from .data_manager import Database
from .sign_manager import SignManager
from .rank_manager import RankImageGenerator
from .profile_generator import ProfileImageGenerator
from .anti_spam import AntiSpam
from .video_parser import parse_video
from .video_girl import GirlVideoManager
from .utils import get_ats, get_reply_text, parse_bool, get_nickname, download_file

# 定义菜单分类
CATEGORIES = [
    {
        "name": "个人中心",
        "key": "个人",
        "admin_only": False,
        "items": [
            {"cmd": "个人信息", "desc": "查看个人信息（可引用查看他人）"},
            {"cmd": "签到", "desc": "每日签到得积分"},
            {"cmd": "积分", "desc": "查看当前积分"}
        ]
    },
    {
        "name": "排行榜",
        "key": "排行",
        "admin_only": False,
        "items": [
            {"cmd": "积分榜", "desc": "积分排行榜"},
            {"cmd": "签到榜", "desc": "签到天数榜"},
            {"cmd": "使用榜", "desc": "免禁言卡使用榜"}
        ]
    },
    {
        "name": "视频解析",
        "key": "视频",
        "admin_only": False,
        "items": [
            {"cmd": "解析", "desc": "解析视频/图文链接（发送 解析 [链接]）"},
            {"cmd": "小姐姐视频", "desc": "获取随机小姐姐视频"}
        ]
    },
    {
        "name": "群管理",
        "key": "群管",
        "admin_only": True,
        "items": [
            {"cmd": "全员禁言", "desc": "开启全员禁言"},
            {"cmd": "关闭全员禁言", "desc": "关闭全员禁言"},
            {"cmd": "禁言 QQ号 [秒数]", "desc": "禁言用户"},
            {"cmd": "解禁 QQ号", "desc": "解除禁言"},
            {"cmd": "踢人 QQ号", "desc": "踢出用户"},
            {"cmd": "拉黑 QQ号", "desc": "踢出并拉黑"}
        ]
    }
]

@register(
    name="astrbot_plugin_multigroup",
    author="YourName",
    desc="多功能群管理（签到、积分、刷屏检测、视频解析、图片菜单 + 群管功能 + 个人信息图片 + 小姐姐视频）",
    version="3.4.0"
)
class MultiGroupPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.context = context
        self.config_dict = config or {}
        self.plugin_dir = Path(__file__).parent
        try:
            self.data_dir = Path(StarTools.get_data_dir("astrbot_plugin_multigroup"))
        except:
            self.data_dir = Path(context.base_dir) / "data" / "plugins" / "astrbot_plugin_multigroup"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.plugin_config = PluginConfig.from_dict(self.config_dict, self.plugin_dir, self.data_dir)

        self.db = Database(self.data_dir / "multigroup.db")

        self.sign_mgr = SignManager(self.db, self.plugin_config)
        self.rank_gen = RankImageGenerator(
            str(self.plugin_dir),
            str(self.data_dir),
            self.plugin_config.background_image,
            self.plugin_config.font_file
        )
        self.profile_gen = ProfileImageGenerator(
            str(self.plugin_dir),
            str(self.data_dir),
            self.plugin_config.background_image,
            self.plugin_config.font_file,
            self.plugin_config.profile_blur_radius
        )
        self.anti_spam = AntiSpam(self.db, self.plugin_config)

        # 初始化小姐姐视频管理器
        self.girl_video_mgr = GirlVideoManager(self.plugin_config)

        self.ban_me_quotes = self.plugin_config.ban_me_quotes

        logger.info(f"多功能群管理插件 v3.4.0 加载成功，数据目录: {self.data_dir}")

    def is_admin(self, user_id: str) -> bool:
        return user_id in self.plugin_config.admin_qqs

    def is_group_allowed(self, group_id: str) -> bool:
        whitelist = self.plugin_config.group_whitelist
        if not whitelist:
            return True
        return group_id in whitelist

    def get_cmd(self, text: str) -> tuple[str, str]:
        prefix = self.plugin_config.command_prefix
        if prefix and not text.startswith(prefix):
            return "", ""
        if prefix:
            text = text[len(prefix):]
        parts = text.strip().split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""
        return cmd, args

    async def send_by_style(self, event: AstrMessageEvent, style: str, text: str, title: str = ""):
        if style == "图片":
            lines = text.split("\n")
            if title.startswith("📋") or title.startswith("⚙️") or title.startswith("📂"):
                img_path = await self.rank_gen.create_menu_image(
                    title, lines,
                    blur_radius=self.plugin_config.menu_blur_radius,
                    title_color=self.plugin_config.title_color,
                    text_color=self.plugin_config.text_color
                )
            elif "排行榜" in title:
                img_path = await self.rank_gen.create_rank_image(
                    title, lines, self.plugin_config.rank_max_lines,
                    blur_radius=self.plugin_config.rank_blur_radius,
                    title_color=self.plugin_config.title_color,
                    text_color=self.plugin_config.text_color
                )
            else:
                img_path = await self.rank_gen.create_menu_image(
                    title, lines,
                    blur_radius=self.plugin_config.menu_blur_radius,
                    title_color=self.plugin_config.title_color,
                    text_color=self.plugin_config.text_color
                )
            if img_path:
                await event.send(event.image_result(img_path))
                return
        await event.send(event.plain_result(text))

    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AiocqhttpMessageEvent):
        group_id = event.get_group_id()
        if not self.is_group_allowed(group_id):
            return

        text = event.message_str.strip()
        cmd, args = self.get_cmd(text)

        if self.plugin_config.enable_spam_detect:
            asyncio.create_task(self.anti_spam.check(event))

        if cmd == "菜单":
            await self.show_category_list(event)
            return

        for cat in CATEGORIES:
            if cmd == cat["key"].lower():
                if cat["admin_only"] and not self.is_admin(event.get_sender_id()):
                    await event.send(event.plain_result("你没有权限查看此分类。"))
                    return
                await self.show_category_items(event, cat)
                return

        found_cmd = None
        cmd_lower = cmd
        for cat in CATEGORIES:
            for item in cat["items"]:
                base_cmd = item["cmd"].split()[0].lower()
                if cmd_lower == base_cmd:
                    if item.get("admin_only", False) or cat["admin_only"]:
                        if not self.is_admin(event.get_sender_id()):
                            await event.send(event.plain_result("你没有权限使用此命令。"))
                            return
                    found_cmd = item["cmd"]
                    break
            if found_cmd:
                break

        if not found_cmd:
            return

        if cmd == "个人信息":
            await self.handle_profile(event)
        elif cmd == "签到" and self.plugin_config.enable_sign:
            await self.handle_sign(event)
        elif cmd == "积分":
            await self.handle_points(event)
        elif cmd == "积分榜" and self.plugin_config.enable_rank:
            await self.handle_points_rank(event)
        elif cmd == "签到榜" and self.plugin_config.enable_rank:
            await self.handle_sign_rank(event)
        elif cmd == "使用榜" and self.plugin_config.enable_rank:
            await self.handle_use_rank(event)
        elif cmd == "解析":
            await self.handle_parse(event, args)
        elif cmd == "小姐姐视频" and self.plugin_config.enable_girl_video:
            await self.handle_girl_video(event)
        elif self.is_admin(event.get_sender_id()):
            if cmd == "全员禁言" and self.plugin_config.enable_mute_all:
                await self.handle_mute_all(event, args)
            elif cmd == "关闭全员禁言" and self.plugin_config.enable_mute_all:
                await self.handle_disable_mute_all(event)
            elif cmd == "禁言" and self.plugin_config.enable_ban:
                await self.handle_ban(event, args)
            elif cmd == "解禁" and self.plugin_config.enable_ban:
                await self.handle_unban(event, args)
            elif cmd == "踢人" and self.plugin_config.enable_kick:
                await self.handle_kick(event, args)
            elif cmd == "拉黑" and self.plugin_config.enable_block:
                await self.handle_block(event, args)

    # ---------- 修改后的菜单显示函数：直接显示所有命令，两列布局，每行用 | 分隔 ----------
    async def show_category_list(self, event: AiocqhttpMessageEvent):
        # 从配置获取标题和额外居中文本
        title = self.plugin_config.menu_title
        extra_center = self.plugin_config.menu_extra_center

        lines = [f"———{title}———"]

        # 收集所有可用的命令（只取命令名，不含描述）
        all_items = []
        for cat in CATEGORIES:
            if cat["admin_only"] and not self.is_admin(event.get_sender_id()):
                continue
            for item in cat["items"]:
                all_items.append(item['cmd'])  # 只取命令名

        # 两列布局，每行两个命令用 | 分隔，右侧为空时也显示 |
        half = (len(all_items) + 1) // 2
        left_col = all_items[:half]
        right_col = all_items[half:] + [''] * (half - len(all_items[half:]))  # 右侧补齐空字符串

        for left, right in zip(left_col, right_col):
            if right:
                line = f"{left} | {right}"
            else:
                line = f"{left} |"   # 右侧为空时也显示 |
            lines.append(line)

        # 添加额外的居中文本（如果配置不为空）
        if extra_center:
            # 简单居中：根据标题长度计算缩进
            title_len = len(title)
            center_len = len(extra_center)
            indent = max(0, (title_len + 6 - center_len) // 2)  # 6 是两侧的破折号数量
            lines.append(" " * indent + extra_center)

        text = "\n".join(lines)
        await self.send_by_style(event, self.plugin_config.menu_style, text, "菜单")

    async def show_category_items(self, event: AiocqhttpMessageEvent, category: dict):
        lines = [f"【{category['name']}】", ""]
        for item in category["items"]:
            lines.append(f"{item['cmd']} - {item['desc']}")
        if len(lines) == 2:
            lines.append("该分类下暂无功能。")
        title = f"{category['name']}"
        style = self.plugin_config.menu_style
        await self.send_by_style(event, style, "\n".join(lines), title)

    # ---------- 视频解析处理函数（合并转发版） ----------
    async def handle_parse(self, event: AiocqhttpMessageEvent, args: str):
        if not args:
            await event.send(event.plain_result("请发送要解析的视频链接，例如：解析 https://v.douyin.com/xxx"))
            return

        await event.send(event.plain_result("正在解析并下载，请稍候..."))

        result = await parse_video(args)
        if not result['success']:
            await event.send(event.plain_result(f"解析失败：{result['message']}"))
            return

        data = result['data']
        platform_map = {
            'douyin': '抖音',
            'kuaishou': '快手',
            'bilibili': 'B站',
            'xiaohongshu': '小红书'
        }
        platform_name = platform_map.get(data['platform'], data['platform'])

        temp_dir = self.data_dir / "temp"
        temp_dir.mkdir(exist_ok=True)

        downloaded_files = []
        nodes = []

        self_uin = event.get_self_id()
        author_name = data.get('nickName', platform_name)

        try:
            if data['type'] == 1:  # 视频
                text = f"📹 {platform_name} 视频解析结果\n标题：{data['title']}\n作者：{author_name}"
                text_node = {
                    "type": "node",
                    "data": {
                        "name": author_name,
                        "uin": self_uin,
                        "content": [{"type": "text", "data": {"text": text}}]
                    }
                }
                nodes.append(text_node)

                if data.get('cover'):
                    cover_url = data['cover']
                    cover_file = temp_dir / f"cover_{int(time.time())}.jpg"
                    downloaded = await download_file(cover_url, cover_file)
                    if downloaded:
                        downloaded_files.append(cover_file)
                        cover_node = {
                            "type": "node",
                            "data": {
                                "name": author_name,
                                "uin": self_uin,
                                "content": [{"type": "image", "data": {"file": str(cover_file)}}]
                            }
                        }
                        nodes.append(cover_node)

                video_url = data['videoUrl']
                video_ext = ".mp4"
                video_file = temp_dir / f"video_{int(time.time())}{video_ext}"
                downloaded_video = await download_file(video_url, video_file)
                if not downloaded_video:
                    raise Exception("视频下载失败")
                downloaded_files.append(video_file)

                video_node = {
                    "type": "node",
                    "data": {
                        "name": author_name,
                        "uin": self_uin,
                        "content": [{"type": "video", "data": {"file": str(video_file)}}]
                    }
                }
                nodes.append(video_node)

            else:  # 图集
                image_list = data.get('imageList', [])
                if not image_list:
                    await event.send(event.plain_result("解析成功，但未找到图片"))
                    return

                text = f"📸 {platform_name} 图文解析结果\n标题：{data['title']}\n作者：{author_name}\n共 {len(image_list)} 张图片"
                text_node = {
                    "type": "node",
                    "data": {
                        "name": author_name,
                        "uin": self_uin,
                        "content": [{"type": "text", "data": {"text": text}}]
                    }
                }
                nodes.append(text_node)

                max_images = 5
                for idx, img_url in enumerate(image_list[:max_images]):
                    img_file = temp_dir / f"image_{int(time.time())}_{idx}.jpg"
                    downloaded = await download_file(img_url, img_file)
                    if downloaded:
                        downloaded_files.append(img_file)
                        img_node = {
                            "type": "node",
                            "data": {
                                "name": author_name,
                                "uin": self_uin,
                                "content": [{"type": "image", "data": {"file": str(img_file)}}]
                            }
                        }
                        nodes.append(img_node)

                if len(image_list) > max_images:
                    extra_node = {
                        "type": "node",
                        "data": {
                            "name": author_name,
                            "uin": self_uin,
                            "content": [{"type": "text", "data": {"text": f"还有 {len(image_list)-max_images} 张图片未显示"}}]
                        }
                    }
                    nodes.append(extra_node)

            if nodes:
                group_id = int(event.get_group_id())
                try:
                    await event.bot.api.call_action(
                        "send_group_forward_msg",
                        group_id=group_id,
                        messages=nodes
                    )
                except Exception as e:
                    logger.error(f"发送合并转发失败: {e}")
                    await event.send(event.plain_result("合并转发发送失败，尝试直接发送..."))
                    await event.send(event.plain_result(text))
                    for node in nodes[1:]:
                        content = node["data"]["content"][0]
                        if content["type"] == "image":
                            await event.send(event.image_result(content["data"]["file"]))
                        elif content["type"] == "video":
                            await event.send(event.video_result(content["data"]["file"]))
            else:
                await event.send(event.plain_result("没有可发送的内容"))

        except Exception as e:
            logger.error(f"解析/下载失败: {e}")
            await event.send(event.plain_result(f"处理失败：{str(e)}"))
        finally:
            for f in downloaded_files:
                try:
                    f.unlink(missing_ok=True)
                except:
                    pass

    # ---------- 小姐姐视频处理函数 ----------
    async def handle_girl_video(self, event: AiocqhttpMessageEvent):
        if not self.plugin_config.enable_girl_video:
            await event.send(event.plain_result("小姐姐视频功能已关闭"))
            return

        await event.send(event.plain_result("正在获取随机小姐姐视频，请稍候..."))

        video_url = await self.girl_video_mgr.get_video_url()
        if not video_url:
            await event.send(event.plain_result("获取视频失败，请稍后重试"))
            return

        if self.plugin_config.girl_video_download_video:
            temp_dir = self.data_dir / "temp"
            temp_dir.mkdir(exist_ok=True)
            video_file = temp_dir / f"girl_video_{int(time.time())}.mp4"
            downloaded = await download_file(video_url, video_file)
            if not downloaded:
                await event.send(event.plain_result("视频下载失败"))
                return

            try:
                if self.plugin_config.girl_video_send_as_forward:
                    self_uin = event.get_self_id()
                    nodes = [
                        {
                            "type": "node",
                            "data": {
                                "name": "小姐姐视频",
                                "uin": self_uin,
                                "content": [{"type": "video", "data": {"file": str(video_file)}}]
                            }
                        }
                    ]
                    await event.bot.api.call_action(
                        "send_group_forward_msg",
                        group_id=int(event.get_group_id()),
                        messages=nodes
                    )
                else:
                    await event.send(event.video_result(str(video_file)))
            except Exception as e:
                logger.error(f"发送视频失败: {e}")
                await event.send(event.plain_result(f"发送失败: {e}"))
            finally:
                try:
                    video_file.unlink(missing_ok=True)
                except:
                    pass
        else:
            await event.send(event.plain_result(f"小姐姐视频链接：{video_url}"))

    # ---------- 个人信息 ----------
    async def handle_profile(self, event: AiocqhttpMessageEvent):
        target_id = None
        first_seg = event.get_messages()[0] if event.get_messages() else None
        if isinstance(first_seg, Reply):
            try:
                reply_msg_id = first_seg.id
                payload = {
                    "group_id": int(event.get_group_id()),
                    "message_seq": int(reply_msg_id),
                    "count": 1,
                    "reverseOrder": False
                }
                result = await event.bot.api.call_action("get_group_msg_history", **payload)
                if result.get("messages"):
                    target_id = str(result["messages"][0]["sender"]["user_id"])
            except:
                pass

        if not target_id:
            target_id = event.get_sender_id()

        group_id = event.get_group_id()
        user = self.db.get_user(group_id, target_id)

        purchases = self.db.get_user_purchases(target_id)
        items = {}
        for p in purchases:
            item = self.db.get_item(p["item_id"])
            if item:
                name = item["name"]
                items[name] = items.get(name, 0) + p["quantity"]
        items_list = [(name, qty) for name, qty in items.items()]

        points_rank_data = self.db.get_points_rank(group_id, 1000)
        sign_rank_data = self.db.get_sign_rank(group_id, 1000)
        use_rank_data = self.db.get_card_usage_rank(group_id, 1000)

        def get_rank(data, uid):
            for i, (user_id, _) in enumerate(data, 1):
                if user_id == uid:
                    return i
            return None

        rank_info = {
            "points_rank": get_rank(points_rank_data, target_id) or "未上榜",
            "sign_rank": get_rank(sign_rank_data, target_id) or "未上榜",
            "use_rank": get_rank(use_rank_data, target_id) or "未上榜",
        }

        nickname = await get_nickname(event, target_id) if event.get_group_id() else target_id

        if self.plugin_config.profile_style == "图片":
            img_path = await self.profile_gen.create_profile_image(
                target_id,
                nickname,
                user["points"],
                user["sign_count"],
                items_list,
                rank_info,
                self.plugin_config
            )
            if img_path:
                await event.send(event.image_result(img_path))
                return

        msg = f"【个人信息】\n昵称：{nickname}\nQQ：{target_id}\n积分：{user['points']}\n签到次数：{user['sign_count']}\n拥有商品："
        if items_list:
            msg += " ".join([f"{n}×{q}" for n,q in items_list])
        else:
            msg += "无"
        msg += f"\n积分排名：{rank_info['points_rank']}\n签到排名：{rank_info['sign_rank']}\n使用排名：{rank_info['use_rank']}"
        await event.send(event.plain_result(msg))

    # ---------- 签到 ----------
    async def handle_sign(self, event: AiocqhttpMessageEvent):
        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        ok, msg, points = await self.sign_mgr.process(group_id, user_id)
        if ok:
            style = self.plugin_config.sign_style
            await self.send_by_style(event, style, msg, "签到成功")
        else:
            await event.send(event.plain_result(msg))

    # ---------- 积分 ----------
    async def handle_points(self, event: AiocqhttpMessageEvent):
        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        user = self.db.get_user(group_id, user_id)
        await event.send(event.plain_result(f"你的积分：{user['points']}"))

    # ---------- 积分排行榜 ----------
    async def handle_points_rank(self, event: AiocqhttpMessageEvent):
        group_id = event.get_group_id()
        data = self.db.get_points_rank(group_id, self.plugin_config.rank_max_lines)
        lines = []
        for i, (uid, points) in enumerate(data, 1):
            nickname = await get_nickname(event, uid) if event.get_group_id() else uid
            lines.append(f"{i}. {nickname} - {points}积分")
        title = self.plugin_config.points_rank_title
        style = self.plugin_config.rank_style
        if style == "图片":
            img = await self.rank_gen.create_rank_image(
                title, lines, self.plugin_config.rank_max_lines,
                blur_radius=self.plugin_config.rank_blur_radius,
                title_color=self.plugin_config.title_color,
                text_color=self.plugin_config.text_color
            )
            if img:
                await event.send(event.image_result(img))
                return
        await event.send(event.plain_result("\n".join([title] + lines)))

    # ---------- 签到排行榜 ----------
    async def handle_sign_rank(self, event: AiocqhttpMessageEvent):
        group_id = event.get_group_id()
        data = self.db.get_sign_rank(group_id, self.plugin_config.rank_max_lines)
        lines = []
        for i, (uid, cnt) in enumerate(data, 1):
            nickname = await get_nickname(event, uid) if event.get_group_id() else uid
            lines.append(f"{i}. {nickname} - {cnt}天")
        title = self.plugin_config.sign_rank_title
        style = self.plugin_config.rank_style
        if style == "图片":
            img = await self.rank_gen.create_rank_image(
                title, lines, self.plugin_config.rank_max_lines,
                blur_radius=self.plugin_config.rank_blur_radius,
                title_color=self.plugin_config.title_color,
                text_color=self.plugin_config.text_color
            )
            if img:
                await event.send(event.image_result(img))
                return
        await event.send(event.plain_result("\n".join([title] + lines)))

    # ---------- 使用榜 ----------
    async def handle_use_rank(self, event: AiocqhttpMessageEvent):
        group_id = event.get_group_id()
        data = self.db.get_card_usage_rank(group_id, self.plugin_config.rank_max_lines)
        lines = []
        for i, (uid, used) in enumerate(data, 1):
            nickname = await get_nickname(event, uid) if event.get_group_id() else uid
            lines.append(f"{i}. {nickname} - 使用{used}次")
        title = self.plugin_config.use_rank_title
        style = self.plugin_config.rank_style
        if style == "图片":
            img = await self.rank_gen.create_rank_image(
                title, lines, self.plugin_config.rank_max_lines,
                blur_radius=self.plugin_config.rank_blur_radius,
                title_color=self.plugin_config.title_color,
                text_color=self.plugin_config.text_color
            )
            if img:
                await event.send(event.image_result(img))
                return
        await event.send(event.plain_result("\n".join([title] + lines)))

    # ---------- 禁言 ----------
    async def handle_ban(self, event: AiocqhttpMessageEvent, args: str):
        if not self.plugin_config.enable_ban:
            await event.send(event.plain_result("禁言功能已关闭"))
            return
        parts = args.split()
        if not parts:
            await event.send(event.plain_result("请提供QQ号，例如：禁言 123456 60"))
            return
        target_id = parts[0]
        if not target_id.isdigit():
            await event.send(event.plain_result("QQ号格式错误"))
            return
        duration = 600
        if len(parts) > 1 and parts[1].isdigit():
            duration = int(parts[1])
        try:
            await event.bot.set_group_ban(
                group_id=int(event.get_group_id()),
                user_id=int(target_id),
                duration=duration
            )
            self.db.add_mute_record(
                target_id, event.get_group_id(), "admin", f"管理员禁言 {duration}秒",
                duration, int(time.time()), int(time.time()) + duration
            )
            await event.send(event.plain_result(f"已禁言用户 {target_id} 时长 {duration} 秒"))
        except Exception as e:
            await event.send(event.plain_result(f"禁言失败: {e}"))

    # ---------- 解禁 ----------
    async def handle_unban(self, event: AiocqhttpMessageEvent, args: str):
        if not self.plugin_config.enable_ban:
            await event.send(event.plain_result("解禁功能已关闭"))
            return
        target_id = args.strip()
        if not target_id or not target_id.isdigit():
            await event.send(event.plain_result("请提供QQ号，例如：解禁 123456"))
            return
        try:
            await event.bot.set_group_ban(
                group_id=int(event.get_group_id()),
                user_id=int(target_id),
                duration=0
            )
            await event.send(event.plain_result(f"已解禁用户 {target_id}"))
        except Exception as e:
            await event.send(event.plain_result(f"解禁失败: {e}"))

    # ---------- 踢人 ----------
    async def handle_kick(self, event: AiocqhttpMessageEvent, args: str):
        if not self.plugin_config.enable_kick:
            await event.send(event.plain_result("踢人功能已关闭"))
            return
        target_id = args.strip()
        if not target_id or not target_id.isdigit():
            await event.send(event.plain_result("请提供QQ号，例如：踢人 123456"))
            return
        try:
            await event.bot.set_group_kick(
                group_id=int(event.get_group_id()),
                user_id=int(target_id),
                reject_add_request=False
            )
            await event.send(event.plain_result(f"已踢出用户 {target_id}"))
        except Exception as e:
            await event.send(event.plain_result(f"踢出失败: {e}"))

    # ---------- 拉黑 ----------
    async def handle_block(self, event: AiocqhttpMessageEvent, args: str):
        if not self.plugin_config.enable_block:
            await event.send(event.plain_result("拉黑功能已关闭"))
            return
        target_id = args.strip()
        if not target_id or not target_id.isdigit():
            await event.send(event.plain_result("请提供QQ号，例如：拉黑 123456"))
            return
        try:
            await event.bot.set_group_kick(
                group_id=int(event.get_group_id()),
                user_id=int(target_id),
                reject_add_request=True
            )
            await event.send(event.plain_result(f"已拉黑用户 {target_id}"))
        except Exception as e:
            await event.send(event.plain_result(f"拉黑失败: {e}"))

    # ---------- 全员禁言 ----------
    async def handle_mute_all(self, event: AiocqhttpMessageEvent, args: str):
        if not self.plugin_config.enable_mute_all:
            await event.send(event.plain_result("全员禁言功能已关闭"))
            return
        try:
            await event.bot.set_group_whole_ban(group_id=int(event.get_group_id()), enable=True)
            await event.send(event.plain_result("已开启全员禁言"))
        except Exception as e:
            await event.send(event.plain_result(f"操作失败: {e}"))

    # ---------- 关闭全员禁言 ----------
    async def handle_disable_mute_all(self, event: AiocqhttpMessageEvent):
        if not self.plugin_config.enable_mute_all:
            await event.send(event.plain_result("全员禁言功能已关闭"))
            return
        try:
            await event.bot.set_group_whole_ban(group_id=int(event.get_group_id()), enable=False)
            await event.send(event.plain_result("已关闭全员禁言"))
        except Exception as e:
            await event.send(event.plain_result(f"操作失败: {e}"))