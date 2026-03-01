# coer/utils.py
import re
import time
import random
from typing import List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import aiohttp
from astrbot.api import logger
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
from astrbot.core.message.components import At, Reply, Image

def get_ats(event: AiocqhttpMessageEvent) -> List[str]:
    ats = []
    try:
        for seg in event.message_obj.message:
            if seg.type == "at" and seg.data.get("qq") != "all":
                ats.append(str(seg.data["qq"]))
    except:
        pass
    return ats

def extract_image_url(chain) -> Optional[str]:
    for seg in chain:
        if isinstance(seg, Image):
            return seg.url or seg.file
        if isinstance(seg, Reply):
            for sub in seg.chain:
                if isinstance(sub, Image):
                    return sub.url or sub.file
    return None

def get_reply_text(event: AiocqhttpMessageEvent) -> str:
    try:
        first = event.message_obj.message[0]
        if isinstance(first, Reply):
            for sub in first.chain:
                if hasattr(sub, 'text'):
                    return sub.text
    except:
        pass
    return ""

async def get_nickname(event: AiocqhttpMessageEvent, user_id: str) -> str:
    try:
        info = await event.bot.get_group_member_info(
            group_id=int(event.get_group_id()),
            user_id=int(user_id),
            no_cache=True
        )
        card = info.get("card", "").strip()
        nickname = info.get("nickname", "").strip()
        return card or nickname or user_id
    except:
        return user_id

async def download_file(url: str, save_path: Path, headers: dict = None) -> Optional[Path]:
    """
    下载文件，支持自定义 headers，并添加更完整的浏览器请求头以绕过防盗链
    :param url: 文件URL
    :param save_path: 保存路径
    :param headers: 请求头（可选）
    :return: 成功返回 Path，否则返回 None
    """
    try:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 构建完整的请求头
        full_headers = {
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
        
        # 如果调用者提供了 headers，则合并（调用者的 headers 会覆盖默认值）
        if headers:
            full_headers.update(headers)
        
        # 确保有 Referer，如果没有则添加一个通用的
        if 'Referer' not in full_headers:
            full_headers['Referer'] = 'https://www.douyin.com/'
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=full_headers, timeout=30, allow_redirects=True) as resp:
                if resp.status == 200:
                    save_path.write_bytes(await resp.read())
                    return save_path
                else:
                    logger.error(f"下载失败，HTTP {resp.status} - {url}")
                    # 打印响应头以便调试
                    logger.debug(f"响应头: {dict(resp.headers)}")
    except Exception as e:
        logger.error(f"下载异常: {e} - {url}")
    return None

def parse_bool(val) -> Optional[bool]:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        v = val.lower().strip()
        if v in ("true", "1", "yes", "on", "开", "开启"):
            return True
        if v in ("false", "0", "no", "off", "关", "关闭"):
            return False
    return None

def format_time(timestamp: int) -> str:
    if not timestamp:
        return "未知"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

def extract_target_ids(event: AiocqhttpMessageEvent, args: str) -> List[str]:
    """
    从命令参数中提取目标QQ号列表，支持@和数字。
    返回用户ID列表（字符串）。
    """
    target_ids = []
    # 先找@
    ats = get_ats(event)
    target_ids.extend(ats)

    # 再从参数中解析数字
    for part in args.split():
        part = part.strip()
        if part.isdigit():
            target_ids.append(part)

    # 去重
    return list(set(target_ids))

def get_reply_message_id(event: AiocqhttpMessageEvent) -> Optional[str]:
    """获取被回复的消息ID"""
    try:
        first = event.message_obj.message[0]
        if isinstance(first, Reply):
            return first.id
    except:
        pass
    return None