# astrbot_plugin_YOTO/main.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
import asyncio
import random
import time
import re
import aiohttp
import zipfile  # 用于压缩文件
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Union

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
from astrbot.core.star.filter.event_message_type import EventMessageType
from astrbot.core.message.components import Reply, Plain, Image, Video, File, Node, Nodes

try:
    from astrbot.api.message import MessageChain
except ImportError:
    try:
        from astrbot.core.message.components import MessageChain
        logger.info("从 core.message.components 导入 MessageChain")
    except ImportError:
        MessageChain = None
        logger.warning("MessageChain 导入失败，合并转发可能无法使用")

from coer.config import PluginConfig
from coer.data_manager import Database
from coer.sign_manager import SignManager
from coer.rank_manager import RankImageGenerator
from coer.profile_generator import ProfileImageGenerator
from coer.anti_spam import AntiSpam
from coer.video_parser import parse_video as video_parser_func
from coer.utils import (
    get_ats, get_reply_text, parse_bool, get_nickname, download_file,
    extract_target_ids, get_reply_message_id
)
from coer.curfew import CurfewHandle

# ----- 合并转发函数 -----
async def send_forward_message(bot, target_id: int, messages: List[tuple], target_type: str = "group"):
    """
    发送合并转发消息（支持视频、图片、文件等）
    
    :param bot: AstrBot 的 bot 实例
    :param target_id: 目标群号或好友 QQ 号
    :param messages: 消息列表，每个元素为 (发送者QQ, 发送者昵称, 消息内容)
                     消息内容可以是 str 或 List[Dict]（消息段列表）
    :param target_type: "group" 或 "private"
    """
    nodes = []
    for uid, nickname, content in messages:
        node = {
            "type": "node",
            "data": {
                "user_id": uid,
                "nickname": nickname,
                "content": content
            }
        }
        nodes.append(node)
    
    if target_type == "group":
        await bot.send_group_forward_msg(group_id=target_id, messages=nodes)
    else:
        await bot.send_private_forward_msg(user_id=target_id, messages=nodes)

# ----- 用户菜单分类（已移除使用榜） -----
USER_CATEGORIES = [
    {
        "name": "个人中心",
        "key": "个人",
        "items": [
            {"cmd": "个人信息", "desc": "查看个人信息（可引用查看他人）"},
            {"cmd": "签到", "desc": "每日签到得积分"},
            {"cmd": "积分", "desc": "查看当前积分"}
        ]
    },
    {
        "name": "排行榜",
        "key": "排行",
        "items": [
            {"cmd": "积分榜", "desc": "积分排行榜"},
            {"cmd": "签到榜", "desc": "签到天数榜"}
        ]
    },
    {
        "name": "视频解析",
        "key": "视频",
        "items": [
            {"cmd": "解析", "desc": "解析视频/图文链接（支持抖音/快手/B站/小红书/微博/头条/皮皮虾）"}
        ]
    }
]

ADMIN_CATEGORIES = [
    {
        "name": "群管理",
        "key": "群管",
        "items": [
            {"cmd": "全员禁言", "desc": "开启全员禁言"},
            {"cmd": "关闭全员禁言", "desc": "关闭全员禁言"},
            {"cmd": "禁言", "desc": "禁言用户：禁言 [@/QQ号] [秒数]"},
            {"cmd": "解禁", "desc": "解除禁言：解禁 [@/QQ号]"},
            {"cmd": "踢人", "desc": "踢出用户：踢人 [@/QQ号]"},
            {"cmd": "拉黑", "desc": "踢出并拉黑：拉黑 [@/QQ号]"},
            {"cmd": "撤回", "desc": "撤回消息：撤回 [数量]（需引用或@）"},
            {"cmd": "开启宵禁", "desc": "开启宵禁 [HH:MM HH:MM]（留空使用默认时间）"},
            {"cmd": "关闭宵禁", "desc": "关闭本群宵禁"}
        ]
    }
]

@register(
    name="astrbot_plugin_multigroup",
    author="感情",
    desc="QQ号多功能群管理",
    version="1.5"
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

        self.curfew = CurfewHandle(self.context, self.plugin_config)
        self.ban_me_quotes = self.plugin_config.ban_me_quotes

        asyncio.create_task(self.curfew.initialize())
        # 已移除加载成功提示语

    def is_admin(self, user_id: str) -> bool:
        return user_id in self.plugin_config.admin_qqs

    def is_group_allowed(self, group_id: str) -> bool:
        """
        检查群是否在白名单中。
        如果白名单为空列表，则所有群都禁止使用（需要显式填写白名单）。
        """
        whitelist = self.plugin_config.group_whitelist
        # 如果白名单为空，表示所有群都不允许
        if not whitelist:
            return False
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
            await self.show_user_menu(event)
            return
        if cmd == "管理员菜单":
            if not self.is_admin(event.get_sender_id()):
                await event.send(event.plain_result("你没有权限查看管理员菜单。"))
                return
            await self.show_admin_menu(event)
            return

        for cat in USER_CATEGORIES:
            if cmd == cat["key"].lower():
                await self.show_category_items(event, cat)
                return
        for cat in ADMIN_CATEGORIES:
            if cmd == cat["key"].lower() and self.is_admin(event.get_sender_id()):
                await self.show_category_items(event, cat)
                return

        found_cmd = None
        cmd_lower = cmd
        for cat in USER_CATEGORIES + ADMIN_CATEGORIES:
            for item in cat["items"]:
                base_cmd = item["cmd"].split()[0].lower()
                if cmd_lower == base_cmd:
                    found_cmd = item["cmd"]
                    if cat in ADMIN_CATEGORIES and not self.is_admin(event.get_sender_id()):
                        await event.send(event.plain_result("你没有权限使用此命令。"))
                        return
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
        elif cmd == "解析" and self.plugin_config.enable_video_parse:
            await self.handle_parse(event, args)
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
            elif cmd == "撤回" and getattr(self.plugin_config, 'enable_recall', True):
                await self.handle_recall(event, args)
            elif cmd == "开启宵禁" and self.plugin_config.enable_curfew:
                await self.handle_start_curfew(event, args)
            elif cmd == "关闭宵禁" and self.plugin_config.enable_curfew:
                await self.handle_stop_curfew(event)

    # ==================== 菜单显示（优化居中对齐） ====================
    async def show_user_menu(self, event: AiocqhttpMessageEvent):
        title = self.plugin_config.menu_title
        extra_center = self.plugin_config.menu_extra_center
        
        # 构建两列显示的命令
        all_items = []
        for cat in USER_CATEGORIES:
            for item in cat["items"]:
                all_items.append(item['cmd'])
        
        half = (len(all_items) + 1) // 2
        left_col = all_items[:half]
        right_col = all_items[half:] + [''] * (half - len(all_items[half:]))
        
        # 计算内容的总宽度
        max_left_len = max(len(cmd) for cmd in left_col) if left_col else 0
        max_right_len = max(len(cmd) for cmd in right_col if cmd) if any(right_col) else 0
        # 每列预留4个字符的间距（包括空格和分隔符）
        total_width = max_left_len + max_right_len + 6
        
        # 计算分隔线的长度
        title_len = len(title)
        # 确保分隔线至少和标题一样长，但也不短于内容宽度
        separator_len = max(total_width, title_len + 4)
        separator = "—" * separator_len
        
        # 构建菜单行
        lines = [separator]
        # 标题居中
        title_padding = (separator_len - title_len) // 2
        lines.append(" " * title_padding + title + " " * (separator_len - title_len - title_padding))
        lines.append(separator)
        
        # 生成命令列表
        for left, right in zip(left_col, right_col):
            if right:
                # 计算左侧命令的填充，使两列均匀分布
                left_padded = left.ljust(max_left_len)
                line = f"  {left_padded}  │  {right}  "
            else:
                # 居中显示左侧命令
                left_padded = left.center(separator_len - 4)
                line = f"  {left_padded}  "
            lines.append(line)
        
        # 添加底部居中文本（如果有）
        if extra_center:
            lines.append(separator)
            center_padding = (separator_len - len(extra_center)) // 2
            lines.append(" " * center_padding + extra_center + " " * (separator_len - len(extra_center) - center_padding))
            lines.append(separator)
        else:
            lines.append(separator)
        
        text = "\n".join(lines)
        await self.send_by_style(event, self.plugin_config.menu_style, text, "用户菜单")

    async def show_admin_menu(self, event: AiocqhttpMessageEvent):
        title = "⚙️ 管理员菜单"
        extra_center = self.plugin_config.menu_extra_center
        
        # 构建两列显示的命令
        all_items = []
        for cat in ADMIN_CATEGORIES:
            for item in cat["items"]:
                all_items.append(item['cmd'])
        
        half = (len(all_items) + 1) // 2
        left_col = all_items[:half]
        right_col = all_items[half:] + [''] * (half - len(all_items[half:]))
        
        # 计算内容的总宽度
        max_left_len = max(len(cmd) for cmd in left_col) if left_col else 0
        max_right_len = max(len(cmd) for cmd in right_col if cmd) if any(right_col) else 0
        total_width = max_left_len + max_right_len + 6
        
        # 计算分隔线的长度
        title_len = len(title)
        separator_len = max(total_width, title_len + 4)
        separator = "—" * separator_len
        
        # 构建菜单行
        lines = [separator]
        # 标题居中
        title_padding = (separator_len - title_len) // 2
        lines.append(" " * title_padding + title + " " * (separator_len - title_len - title_padding))
        lines.append(separator)
        
        # 生成命令列表
        for left, right in zip(left_col, right_col):
            if right:
                left_padded = left.ljust(max_left_len)
                line = f"  {left_padded}  │  {right}  "
            else:
                left_padded = left.center(separator_len - 4)
                line = f"  {left_padded}  "
            lines.append(line)
        
        # 添加底部居中文本（如果有）
        if extra_center:
            lines.append(separator)
            center_padding = (separator_len - len(extra_center)) // 2
            lines.append(" " * center_padding + extra_center + " " * (separator_len - len(extra_center) - center_padding))
            lines.append(separator)
        else:
            lines.append(separator)
        
        text = "\n".join(lines)
        await self.send_by_style(event, self.plugin_config.menu_style, text, "管理员菜单")

    async def show_category_items(self, event: AiocqhttpMessageEvent, category: dict):
        lines = [f"【{category['name']}】", ""]
        for item in category["items"]:
            lines.append(f"{item['cmd']} - {item['desc']}")
        if len(lines) == 2:
            lines.append("该分类下暂无功能。")
        title = f"{category['name']}"
        style = self.plugin_config.menu_style
        await self.send_by_style(event, style, "\n".join(lines), title)

    # ==================== 个人功能（已移除购买记录和使用榜） ====================
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
        # 不再获取购买记录
        points_rank_data = self.db.get_points_rank(group_id, 1000)
        sign_rank_data = self.db.get_sign_rank(group_id, 1000)
        def get_rank(data, uid):
            for i, (user_id, _) in enumerate(data, 1):
                if user_id == uid:
                    return i
            return None
        rank_info = {
            "points_rank": get_rank(points_rank_data, target_id) or "未上榜",
            "sign_rank": get_rank(sign_rank_data, target_id) or "未上榜",
        }
        nickname = await get_nickname(event, target_id) if event.get_group_id() else target_id
        if self.plugin_config.profile_style == "图片":
            img_path = await self.profile_gen.create_profile_image(
                target_id,
                nickname,
                user["points"],
                user["sign_count"],
                [],  # 商品列表为空
                rank_info,
                self.plugin_config
            )
            if img_path:
                await event.send(event.image_result(img_path))
                return
        msg = f"【个人信息】\n昵称：{nickname}\nQQ：{target_id}\n积分：{user['points']}\n签到次数：{user['sign_count']}\n"
        msg += f"\n积分排名：{rank_info['points_rank']}\n签到排名：{rank_info['sign_rank']}"
        await event.send(event.plain_result(msg))
        event.stop_event()

    async def handle_sign(self, event: AiocqhttpMessageEvent):
        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        ok, msg, points = await self.sign_mgr.process(group_id, user_id)
        if ok:
            style = self.plugin_config.sign_style
            await self.send_by_style(event, style, msg, "签到成功")
        else:
            await event.send(event.plain_result(msg))
        event.stop_event()

    async def handle_points(self, event: AiocqhttpMessageEvent):
        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        user = self.db.get_user(group_id, user_id)
        await event.send(event.plain_result(f"你的积分：{user['points']}"))
        event.stop_event()

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
                event.stop_event()
                return
        await event.send(event.plain_result("\n".join([title] + lines)))
        event.stop_event()

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
                event.stop_event()
                return
        await event.send(event.plain_result("\n".join([title] + lines)))
        event.stop_event()

    # ==================== 下载辅助函数 ====================
    async def download_with_progress(self, url: str, save_path: Path, headers: dict = None, max_retries: int = 3) -> Optional[Path]:
        """
        带进度提示的文件下载函数
        :param url: 下载URL
        :param save_path: 保存路径
        :param headers: 请求头
        :param max_retries: 最大重试次数
        :return: 成功返回 Path，否则返回 None
        """
        try:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            full_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
            }
            if headers:
                full_headers.update(headers)
            if 'Referer' not in full_headers:
                full_headers['Referer'] = 'https://www.douyin.com/'
            
            async with aiohttp.ClientSession() as session:
                for attempt in range(max_retries):
                    try:
                        async with session.get(url, headers=full_headers, timeout=None) as resp:  # timeout=None 表示无超时限制
                            if resp.status != 200:
                                logger.error(f"下载失败，HTTP {resp.status} - {url}")
                                if attempt < max_retries - 1:
                                    wait_time = 2 ** attempt
                                    logger.info(f"等待 {wait_time} 秒后重试...")
                                    await asyncio.sleep(wait_time)
                                    continue
                                return None
                            
                            # 获取文件大小
                            content_length = resp.content_length
                            if content_length:
                                size_mb = content_length / (1024 * 1024)
                                if size_mb > 10:  # 大于 10MB 时记录日志
                                    logger.info(f"文件大小: {size_mb:.2f} MB")
                            
                            # 分块下载并计算进度
                            with open(save_path, 'wb') as f:
                                downloaded = 0
                                async for chunk in resp.content.iter_chunked(8192):
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    if content_length and downloaded % (1024 * 1024) == 0:  # 每 1MB 记录一次日志
                                        percent = downloaded / content_length * 100
                                        logger.debug(f"下载进度: {percent:.1f}% ({downloaded}/{content_length} bytes)")
                            
                            # 下载完成后检查文件大小
                            if save_path.exists() and save_path.stat().st_size > 0:
                                logger.info(f"文件下载完成: {save_path.name}")
                                return save_path
                            else:
                                logger.error(f"文件下载后为空: {save_path.name}")
                                return None
                            
                    except (aiohttp.ClientConnectorError, asyncio.TimeoutError) as e:
                        logger.error(f"连接错误 (尝试 {attempt+1}/{max_retries}): {e}")
                    except Exception as e:
                        logger.error(f"下载异常 (尝试 {attempt+1}/{max_retries}): {e}")
                    
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        await asyncio.sleep(wait_time)
        except Exception as e:
            logger.error(f"下载函数整体异常: {e}")
        return None

    # ==================== 视频解析（顺序下载，大文件自动压缩） ====================
    def _get_headers_for_platform(self, platform: str) -> dict:
        """为不同平台生成下载所需的请求头，防止防盗链"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        }
        # 不同平台对应的 Referer
        referers = {
            'douyin': 'https://www.douyin.com/',
            'kuaishou': 'https://www.kuaishou.com/',
            'bilibili': 'https://www.bilibili.com/',
            'xiaohongshu': 'https://www.xiaohongshu.com/',
            'weibo': 'https://www.weibo.com/',
            'toutiao': 'https://www.toutiao.com/',
            'pipixia': 'https://www.pipixia.com/'
        }
        if platform in referers:
            headers['Referer'] = referers[platform]
        return headers

    async def handle_parse(self, event: AiocqhttpMessageEvent, args: str):
        print("[main.handle_parse] 开始执行")  # 调试输出
        if not self.plugin_config.enable_video_parse:
            await event.send(event.plain_result("视频解析功能已关闭"))
            event.stop_event()
            return

        if not args:
            await event.send(event.plain_result("请发送要解析的视频链接，例如：解析 https://v.douyin.com/xxx"))
            event.stop_event()
            return

        await event.send(event.plain_result("正在调用API解析，请稍候..."))

        try:
            # 调用 video_parser 中的解析函数
            print("[main.handle_parse] 调用 video_parser_func")
            result = await video_parser_func(args, None)  # 不需要cookies
            print(f"[main.handle_parse] video_parser_func 返回: {result}")
        except Exception as e:
            print(f"[main.handle_parse] 调用 video_parser_func 异常: {e}")
            import traceback
            traceback.print_exc()
            await event.send(event.plain_result(f"解析器调用异常: {str(e)}"))
            event.stop_event()
            return

        if not result.get('success'):
            await event.send(event.plain_result(f"解析失败：{result.get('message', '未知错误')}"))
            event.stop_event()
            return

        data = result.get('data')
        if not data:
            await event.send(event.plain_result("解析成功但未获取到数据"))
            event.stop_event()
            return

        # 打印完整返回数据（调试用）
        logger.info(f"[解析] 解析器返回数据: {data}")

        platform = data.get('platform', 'unknown')
        platform_name = {
            'douyin': '抖音',
            'kuaishou': '快手',
            'bilibili': 'B站',
            'xiaohongshu': '小红书',
            'weibo': '微博',
            'toutiao': '今日头条',
            'pipixia': '皮皮虾'
        }.get(platform, platform)

        temp_dir = self.data_dir / "temp"
        temp_dir.mkdir(exist_ok=True)
        downloaded_files = []
        self_uin = event.get_self_id()

        # 获取作者信息（兼容不同字段名）
        author_name = data.get('nickName')
        if not author_name:
            author_obj = data.get('author')
            if isinstance(author_obj, dict):
                author_name = author_obj.get('name') or author_obj.get('nickname') or ''
            else:
                author_name = ''
        author_name = author_name or "未知作者"
        title = data.get('title', '无标题')

        # 构造消息节点
        forward_messages = []
        text_content = f"🎬 来源: {platform_name}\n📝 标题: {title}\n👤 作者: {author_name}"
        forward_messages.append((self_uin, author_name, text_content))

        headers = self._get_headers_for_platform(platform)

        try:
            # 判断类型
            content_type = data.get('type')
            video_url = None

            # 处理视频类型（type 为 '1' 或 'video' 或存在 url 字段）
            if content_type in ('1', 'video') or data.get('url') or data.get('videoUrl'):
                video_url = data.get('videoUrl') or data.get('url')
                # 下载封面
                cover = data.get('cover')
                if cover:
                    try:
                        cover_file = temp_dir / f"cover_{int(time.time())}_{random.randint(1000,9999)}.jpg"
                        # 使用带进度的下载函数
                        downloaded = await self.download_with_progress(cover, cover_file, headers)
                        if downloaded:
                            downloaded_files.append(cover_file)
                            image_segment = [{
                                "type": "image",
                                "data": {"file": str(cover_file)}
                            }]
                            forward_messages.append((self_uin, author_name, image_segment))
                        else:
                            # 下载失败，尝试直接发送 URL（OneBot 支持图片 URL）
                            logger.info(f"[解析] 封面下载失败，尝试直接发送 URL: {cover}")
                            image_segment = [{
                                "type": "image",
                                "data": {"file": cover, "cache": 0}
                            }]
                            forward_messages.append((self_uin, author_name, image_segment))
                    except Exception as e:
                        logger.error(f"[解析] 封面处理失败: {e}")
                        # 尝试直接发送 URL
                        image_segment = [{
                            "type": "image",
                            "data": {"file": cover, "cache": 0}
                        }]
                        forward_messages.append((self_uin, author_name, image_segment))

            # 处理图集类型
            elif content_type in ('2', 'image', 'images'):
                image_list = data.get('imageList') or data.get('images') or []
                if image_list:
                    max_images = min(5, len(image_list))
                    for idx, img_url in enumerate(image_list[:max_images]):
                        try:
                            ext = ".jpg"
                            if '.' in img_url.split('/')[-1]:
                                possible_ext = img_url.split('/')[-1].split('?')[0].split('.')[-1]
                                if possible_ext.lower() in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                                    ext = f".{possible_ext}"
                            img_file = temp_dir / f"image_{int(time.time())}_{idx}_{random.randint(1000,9999)}{ext}"
                            downloaded = await self.download_with_progress(img_url, img_file, headers)
                            if downloaded:
                                downloaded_files.append(img_file)
                                image_segment = [{
                                    "type": "image",
                                    "data": {"file": str(img_file)}
                                }]
                                forward_messages.append((self_uin, author_name, image_segment))
                            else:
                                # 下载失败，直接发送 URL
                                logger.info(f"[解析] 图片 {idx+1} 下载失败，尝试直接发送 URL: {img_url}")
                                image_segment = [{
                                    "type": "image",
                                    "data": {"file": img_url, "cache": 0}
                                }]
                                forward_messages.append((self_uin, author_name, image_segment))
                        except Exception as e:
                            logger.error(f"[解析] 图片 {idx+1} 处理失败: {e}")
                            # 尝试直接发送 URL
                            image_segment = [{
                                "type": "image",
                                "data": {"file": img_url, "cache": 0}
                            }]
                            forward_messages.append((self_uin, author_name, image_segment))
                    if len(image_list) > max_images:
                        forward_messages.append((self_uin, author_name, f"还有 {len(image_list)-max_images} 张图片未显示"))
                else:
                    await event.send(event.plain_result("解析成功，但未找到图片"))
                    event.stop_event()
                    return

            # 如果既没有视频也没有图集，但有 url 字段，也视为视频
            elif data.get('url') or data.get('videoUrl'):
                video_url = data.get('videoUrl') or data.get('url')
                cover = data.get('cover')
                if cover:
                    try:
                        cover_file = temp_dir / f"cover_{int(time.time())}_{random.randint(1000,9999)}.jpg"
                        downloaded = await self.download_with_progress(cover, cover_file, headers)
                        if downloaded:
                            downloaded_files.append(cover_file)
                            image_segment = [{
                                "type": "image",
                                "data": {"file": str(cover_file)}
                            }]
                            forward_messages.append((self_uin, author_name, image_segment))
                        else:
                            # 下载失败，直接发送 URL
                            logger.info(f"[解析] 封面下载失败，尝试直接发送 URL: {cover}")
                            image_segment = [{
                                "type": "image",
                                "data": {"file": cover, "cache": 0}
                            }]
                            forward_messages.append((self_uin, author_name, image_segment))
                    except Exception as e:
                        logger.error(f"[解析] 封面处理失败: {e}")
                        image_segment = [{
                            "type": "image",
                            "data": {"file": cover, "cache": 0}
                        }]
                        forward_messages.append((self_uin, author_name, image_segment))
            else:
                await event.send(event.plain_result("无法识别的内容类型"))
                event.stop_event()
                return

            # 下载并发送视频（视频单独处理，因为需要提示）
            if video_url:
                try:
                    ext = ".mp4"
                    if '.' in video_url.split('/')[-1]:
                        possible_ext = video_url.split('/')[-1].split('?')[0].split('.')[-1]
                        if possible_ext.lower() in ['mp4', 'flv', 'avi', 'mov', 'mkv']:
                            ext = f".{possible_ext}"
                    video_file = temp_dir / f"video_{int(time.time())}_{random.randint(1000,9999)}{ext}"
                    
                    # 发送下载提示
                    await event.send(event.plain_result("视频文件较大，正在下载中，请稍后..."))
                    
                    # 使用带进度的下载函数
                    downloaded_video = await self.download_with_progress(video_url, video_file, headers)
                    if downloaded_video:
                        file_size = video_file.stat().st_size
                        if file_size > 50 * 1024 * 1024:  # 大于 50MB
                            # 发送压缩提示
                            await event.send(event.plain_result("视频超过50MB，正在压缩为ZIP文件，请稍后..."))
                            # 生成ZIP文件名
                            zip_file = video_file.with_suffix('.zip')
                            try:
                                with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                                    zf.write(video_file, arcname=video_file.name)
                                logger.info(f"视频压缩完成: {zip_file}")
                                # 检查压缩后大小
                                zip_size = zip_file.stat().st_size
                                if zip_size > 100 * 1024 * 1024:  # 压缩后仍大于100MB，放弃发送文件
                                    await event.send(event.plain_result("压缩后文件仍过大，无法发送，请直接访问链接下载"))
                                    forward_messages.append((self_uin, author_name, f"视频下载链接：{video_url}"))
                                    # 清理ZIP文件（原视频稍后统一清理）
                                    zip_file.unlink(missing_ok=True)
                                else:
                                    # 将原视频和ZIP文件都加入清理列表
                                    downloaded_files.append(video_file)
                                    downloaded_files.append(zip_file)
                                    # 在转发消息中添加ZIP文件节点
                                    zip_segment = [{
                                        "type": "file",
                                        "data": {"file": str(zip_file)}
                                    }]
                                    forward_messages.append((self_uin, author_name, zip_segment))
                                    # 同时附加原始链接文本
                                    forward_messages.append((self_uin, author_name, f"视频原始链接（若ZIP无法查看可复制此链接）：{video_url}"))
                            except Exception as e:
                                logger.error(f"压缩视频失败: {e}")
                                # 压缩失败，尝试发送原视频文件
                                downloaded_files.append(video_file)
                                video_segment = [{
                                    "type": "video",
                                    "data": {"file": str(video_file)}
                                }]
                                forward_messages.append((self_uin, author_name, video_segment))
                                # 同时附加链接
                                forward_messages.append((self_uin, author_name, f"视频链接（备用）：{video_url}"))
                        else:
                            # 小于50MB，直接发送视频
                            downloaded_files.append(video_file)
                            video_segment = [{
                                "type": "video",
                                "data": {"file": str(video_file)}
                            }]
                            forward_messages.append((self_uin, author_name, video_segment))
                    else:
                        logger.error("[解析] 视频下载失败")
                        # 视频下载失败，将链接添加到消息中
                        link_text = f"⚠️ 视频下载失败，可直接访问链接: {video_url}"
                        forward_messages.append((self_uin, author_name, link_text))
                except Exception as e:
                    logger.error(f"[解析] 视频下载异常: {e}")
                    link_text = f"⚠️ 视频下载异常，可直接访问链接: {video_url}"
                    forward_messages.append((self_uin, author_name, link_text))

            # 发送
            if not forward_messages:
                await event.send(event.plain_result("没有可发送的内容"))
                event.stop_event()
                return

            if self.plugin_config.video_send_mode == "合并转发":
                try:
                    group_id = int(event.get_group_id())
                    await send_forward_message(event.bot, group_id, forward_messages, target_type="group")
                except Exception as e:
                    logger.error(f"[解析] 合并转发失败，降级发送: {e}")
                    await event.send(event.plain_result("合并转发失败，改用分开发送"))
                    for msg_tuple in forward_messages:
                        _, _, content = msg_tuple
                        if isinstance(content, str):
                            await event.send(event.plain_result(content))
                        elif isinstance(content, list):
                            for seg in content:
                                if seg.get("type") == "image":
                                    file_data = seg["data"]["file"]
                                    if file_data.startswith(('http://', 'https://')):
                                        await event.send(event.plain_result(f"图片链接: {file_data}"))
                                    else:
                                        await event.send(event.image_result(file_data))
                                elif seg.get("type") == "video":
                                    try:
                                        await event.send(event.chain_result([Video(file=seg["data"]["file"])]))
                                    except Exception as e:
                                        logger.error(f"[解析] 发送视频失败: {e}")
                                        await event.send(event.plain_result(f"视频发送失败，请尝试直接访问链接（但无法获取原始URL）"))
                                elif seg.get("type") == "file":
                                    try:
                                        await event.send(event.chain_result([File(file=seg["data"]["file"])]))
                                    except Exception as e:
                                        logger.error(f"[解析] 发送ZIP文件失败: {e}")
                                        await event.send(event.plain_result(f"ZIP文件发送失败，请尝试直接访问视频链接：{video_url}"))
            else:
                for msg_tuple in forward_messages:
                    _, _, content = msg_tuple
                    if isinstance(content, str):
                        await event.send(event.plain_result(content))
                    elif isinstance(content, list):
                        for seg in content:
                            if seg.get("type") == "image":
                                file_data = seg["data"]["file"]
                                if file_data.startswith(('http://', 'https://')):
                                    await event.send(event.plain_result(f"图片链接: {file_data}"))
                                else:
                                    await event.send(event.image_result(file_data))
                            elif seg.get("type") == "video":
                                try:
                                    await event.send(event.chain_result([Video(file=seg["data"]["file"])]))
                                except Exception as e:
                                    logger.error(f"[解析] 发送视频失败: {e}")
                                    await event.send(event.plain_result(f"视频发送失败，请尝试直接访问链接（但无法获取原始URL）"))
                            elif seg.get("type") == "file":
                                try:
                                    await event.send(event.chain_result([File(file=seg["data"]["file"])]))
                                except Exception as e:
                                    logger.error(f"[解析] 发送ZIP文件失败: {e}")
                                    await event.send(event.plain_result(f"ZIP文件发送失败，请尝试直接访问视频链接：{video_url}"))

        except Exception as e:
            logger.error(f"[解析] 处理异常: {e}")
            await event.send(event.plain_result(f"处理失败：{str(e)}"))
        finally:
            for f in downloaded_files:
                try:
                    if f.exists():
                        f.unlink(missing_ok=True)
                except Exception as e:
                    logger.error(f"[解析] 清理文件失败: {e}")
        event.stop_event()

    # ==================== 昵称解析辅助方法 ====================
    async def _resolve_qq_by_nickname(self, event: AiocqhttpMessageEvent, nickname: str) -> Optional[str]:
        """
        通过昵称在群成员中查找对应的QQ号。
        优先匹配群名片(card)，再匹配昵称(nickname)。
        如果找到唯一匹配，返回QQ号；如果找到多个，返回None并发送提示。
        """
        try:
            members = await event.bot.get_group_member_list(group_id=int(event.get_group_id()))
        except Exception as e:
            logger.error(f"获取群成员列表失败: {e}")
            return None

        matched = []
        for member in members:
            # 获取群名片，如果没有则用昵称
            display_name = member.get('card') or member.get('nickname') or ''
            if display_name == nickname:
                matched.append(str(member['user_id']))

        if not matched:
            return None
        elif len(matched) == 1:
            return matched[0]
        else:
            # 多个匹配，提示用户
            await event.send(event.plain_result(f"昵称“{nickname}”在群中有多个成员，请使用QQ号指定：{', '.join(matched)}"))
            return None

    # ==================== 增强的 _get_target_ids ====================
    async def _get_target_ids(self, event: AiocqhttpMessageEvent, args: str, allow_nickname: bool = True) -> List[str]:
        """
        从命令参数中提取目标QQ号列表，支持真正的@、纯数字以及手动输入的昵称（以@开头）。
        返回用户ID列表（字符串）。
        """
        # 1. 获取真正的@
        target_ids = []
        ats = get_ats(event)
        target_ids.extend(ats)

        # 2. 再从参数中解析数字（排除已存在的ID）
        for part in args.split():
            part = part.strip()
            if part.isdigit() and part not in target_ids:
                target_ids.append(part)

        # 3. 如果 allow_nickname 为 True 且没有找到任何目标，尝试解析昵称
        if allow_nickname and not target_ids:
            # 查找以@开头的参数
            for part in args.split():
                if part.startswith('@') and len(part) > 1:
                    nick = part[1:]
                    qq = await self._resolve_qq_by_nickname(event, nick)
                    if qq:
                        target_ids.append(qq)
                    # 如果解析失败或返回None，不继续添加
                    break  # 只处理第一个@昵称，避免混淆

        return list(set(target_ids))  # 去重

    # ==================== 群管理功能 ====================
    async def handle_ban(self, event: AiocqhttpMessageEvent, args: str):
        if not self.plugin_config.enable_ban:
            await event.send(event.plain_result("禁言功能已关闭"))
            event.stop_event()
            return
        target_ids = await self._get_target_ids(event, args, allow_nickname=True)
        if not target_ids:
            await event.send(event.plain_result("请提供要禁言的QQ号、真正的@用户或输入“禁言 @昵称 [秒数]”"))
            event.stop_event()
            return
        parts = args.split()
        duration = 600
        for part in parts:
            if part.isdigit() and part not in target_ids:
                duration = int(part)
                break
        group_id = int(event.get_group_id())
        results = []
        for uid in target_ids:
            try:
                await event.bot.set_group_ban(group_id=group_id, user_id=int(uid), duration=duration)
                self.db.add_mute_record(uid, event.get_group_id(), "admin", f"管理员禁言 {duration}秒", duration, int(time.time()), int(time.time()) + duration)
                results.append(f"✅ {uid} 已禁言 {duration}秒")
            except Exception as e:
                results.append(f"❌ {uid} 禁言失败: {e}")
        await event.send(event.plain_result("\n".join(results)))
        event.stop_event()

    async def handle_unban(self, event: AiocqhttpMessageEvent, args: str):
        if not self.plugin_config.enable_ban:
            await event.send(event.plain_result("解禁功能已关闭"))
            event.stop_event()
            return
        target_ids = await self._get_target_ids(event, args, allow_nickname=True)
        if not target_ids:
            await event.send(event.plain_result("请提供要解禁的QQ号、真正的@用户或输入“解禁 @昵称”"))
            event.stop_event()
            return
        group_id = int(event.get_group_id())
        results = []
        for uid in target_ids:
            try:
                await event.bot.set_group_ban(group_id=group_id, user_id=int(uid), duration=0)
                results.append(f"✅ {uid} 已解禁")
            except Exception as e:
                results.append(f"❌ {uid} 解禁失败: {e}")
        await event.send(event.plain_result("\n".join(results)))
        event.stop_event()

    async def handle_kick(self, event: AiocqhttpMessageEvent, args: str):
        if not self.plugin_config.enable_kick:
            await event.send(event.plain_result("踢人功能已关闭"))
            event.stop_event()
            return
        target_ids = await self._get_target_ids(event, args, allow_nickname=True)
        if not target_ids:
            await event.send(event.plain_result("请提供要踢出的QQ号、真正的@用户或输入“踢人 @昵称”"))
            event.stop_event()
            return
        group_id = int(event.get_group_id())
        results = []
        for uid in target_ids:
            try:
                await event.bot.set_group_kick(group_id=group_id, user_id=int(uid), reject_add_request=False)
                results.append(f"✅ {uid} 已踢出")
            except Exception as e:
                results.append(f"❌ {uid} 踢出失败: {e}")
        await event.send(event.plain_result("\n".join(results)))
        event.stop_event()

    async def handle_block(self, event: AiocqhttpMessageEvent, args: str):
        if not self.plugin_config.enable_block:
            await event.send(event.plain_result("拉黑功能已关闭"))
            event.stop_event()
            return
        target_ids = await self._get_target_ids(event, args, allow_nickname=True)
        if not target_ids:
            await event.send(event.plain_result("请提供要拉黑的QQ号、真正的@用户或输入“拉黑 @昵称”"))
            event.stop_event()
            return
        group_id = int(event.get_group_id())
        results = []
        for uid in target_ids:
            try:
                await event.bot.set_group_kick(group_id=group_id, user_id=int(uid), reject_add_request=True)
                results.append(f"✅ {uid} 已拉黑")
            except Exception as e:
                results.append(f"❌ {uid} 拉黑失败: {e}")
        await event.send(event.plain_result("\n".join(results)))
        event.stop_event()

    async def handle_recall(self, event: AiocqhttpMessageEvent, args: str):
        if not getattr(self.plugin_config, 'enable_recall', True):
            await event.send(event.plain_result("撤回功能已关闭"))
            event.stop_event()
            return

        # 1. 优先检查是否有引用消息
        reply_msg_id = get_reply_message_id(event)
        if reply_msg_id:
            # 直接撤回引用消息
            try:
                await event.bot.delete_msg(message_id=int(reply_msg_id))
                await event.send(event.plain_result("已撤回引用消息"))
            except Exception as e:
                await event.send(event.plain_result(f"撤回失败: {e}"))
            event.stop_event()
            return

        # 2. 否则尝试获取目标用户（@、数字、昵称）
        target_ids = await self._get_target_ids(event, args, allow_nickname=True)
        if not target_ids:
            await event.send(event.plain_result("请使用真正的@（点击成员）、引用一条消息，或者输入“撤回 @昵称 [数量]”来指定要撤回谁的消息"))
            event.stop_event()
            return

        # 3. 解析数量
        count = 1
        parts = args.split()
        for part in parts:
            if part.isdigit() and part not in target_ids:
                count = int(part)
                break
        if count <= 0:
            count = 1
        if count > getattr(self.plugin_config, 'recall_max_count', 10):
            count = self.plugin_config.recall_max_count

        group_id = int(event.get_group_id())
        msgs_to_recall = []

        try:
            for uid in target_ids:
                payload = {"group_id": group_id, "count": 20}
                result = await event.bot.api.call_action("get_group_msg_history", **payload)
                msgs = result.get("messages", [])
                for msg in msgs:
                    if str(msg["sender"]["user_id"]) == uid:
                        msgs_to_recall.append(msg["message_id"])
                        if len(msgs_to_recall) >= count:
                            break
                if len(msgs_to_recall) >= count:
                    break
        except Exception as e:
            await event.send(event.plain_result(f"获取消息失败: {e}"))
            event.stop_event()
            return

        if not msgs_to_recall:
            await event.send(event.plain_result("未找到可撤回的消息"))
            event.stop_event()
            return

        success = []
        failed = []
        for msg_id in msgs_to_recall[:count]:
            try:
                await event.bot.delete_msg(message_id=msg_id)
                success.append(str(msg_id))
            except Exception as e:
                failed.append(f"{msg_id}({e})")

        result_msg = f"撤回完成：成功 {len(success)} 条"
        if failed:
            result_msg += f"，失败 {len(failed)} 条"
        await event.send(event.plain_result(result_msg))
        event.stop_event()

    async def handle_mute_all(self, event: AiocqhttpMessageEvent, args: str):
        if not self.plugin_config.enable_mute_all:
            await event.send(event.plain_result("全员禁言功能已关闭"))
            event.stop_event()
            return
        try:
            await event.bot.set_group_whole_ban(group_id=int(event.get_group_id()), enable=True)
            await event.send(event.plain_result("已开启全员禁言"))
        except Exception as e:
            await event.send(event.plain_result(f"操作失败: {e}"))
        event.stop_event()

    async def handle_disable_mute_all(self, event: AiocqhttpMessageEvent):
        if not self.plugin_config.enable_mute_all:
            await event.send(event.plain_result("全员禁言功能已关闭"))
            event.stop_event()
            return
        try:
            await event.bot.set_group_whole_ban(group_id=int(event.get_group_id()), enable=False)
            await event.send(event.plain_result("已关闭全员禁言"))
        except Exception as e:
            await event.send(event.plain_result(f"操作失败: {e}"))
        event.stop_event()

    # ==================== 宵禁命令 ====================
    async def handle_start_curfew(self, event: AiocqhttpMessageEvent, args: str):
        if not self.plugin_config.enable_curfew:
            await event.send(event.plain_result("宵禁功能已关闭（请在配置中开启）"))
            event.stop_event()
            return

        # 等待宵禁管理器初始化（最多等待 5 秒）
        for _ in range(10):
            if self.curfew.curfew_managers:
                break
            await asyncio.sleep(0.5)
        else:
            await event.send(event.plain_result("宵禁管理器尚未初始化，请稍后再试"))
            event.stop_event()
            return

        parts = args.split()
        if len(parts) >= 2:
            start_time, end_time = parts[0], parts[1]
            await self.curfew.start_curfew(event, start_time, end_time)
        else:
            await self.curfew.start_curfew(event, None, None)
        event.stop_event()

    async def handle_stop_curfew(self, event: AiocqhttpMessageEvent):
        if not self.plugin_config.enable_curfew:
            await event.send(event.plain_result("宵禁功能已关闭（请在配置中开启）"))
            event.stop_event()
            return

        # 等待宵禁管理器初始化
        for _ in range(10):
            if self.curfew.curfew_managers:
                break
            await asyncio.sleep(0.5)
        else:
            await event.send(event.plain_result("宵禁管理器尚未初始化，请稍后再试"))
            event.stop_event()
            return

        await self.curfew.stop_curfew(event)
        event.stop_event()

    async def terminate(self):
        await self.curfew.stop_all_tasks()
        logger.info("插件终止，宵禁任务已清理")