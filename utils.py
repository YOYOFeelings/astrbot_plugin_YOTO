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

async def download_file(url: str, save_path: Path) -> Optional[Path]:
    try:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    save_path.write_bytes(await resp.read())
                    return save_path
    except Exception as e:
        logger.error(f"下载失败: {e}")
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