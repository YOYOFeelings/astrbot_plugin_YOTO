import time
from collections import defaultdict, deque
from astrbot.api import logger
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent

class AntiSpam:
    def __init__(self, db, config):
        self.db = db
        self.config = config
        self.msg_timestamps = defaultdict(lambda: defaultdict(lambda: deque(maxlen=config.spam_count)))
        self.last_banned = defaultdict(lambda: defaultdict(float))

    async def check(self, event: AiocqhttpMessageEvent):
        if not self.config.enable_spam_detect or self.config.spam_ban_time <= 0:
            return
        group_id = event.get_group_id()
        user_id = event.get_sender_id()
        now = time.time()

        if now - self.last_banned[group_id][user_id] < self.config.spam_ban_time:
            return

        deq = self.msg_timestamps[group_id][user_id]
        deq.append(now)
        if len(deq) < self.config.spam_count:
            return

        recent = list(deq)[-self.config.spam_count:]
        intervals = [recent[i+1] - recent[i] for i in range(self.config.spam_count-1)]
        if all(i < self.config.spam_interval for i in intervals):
            await self.apply_ban(event, user_id, group_id, self.config.spam_ban_time, "刷屏")

    async def apply_ban(self, event: AiocqhttpMessageEvent, user_id: str, group_id: str,
                        duration: int, reason: str, operator: str = "bot"):
        try:
            await event.bot.set_group_ban(group_id=int(group_id), user_id=int(user_id), duration=duration)
            start = int(time.time())
            end = start + duration
            self.db.add_mute_record(user_id, group_id, operator, reason, duration, start, end)
            self.last_banned[group_id][user_id] = time.time()
            nickname = await self.get_nickname(event, user_id)
            await event.send(event.plain_result(f"{nickname} 因{reason}被禁言{duration}秒"))
        except Exception as e:
            logger.error(f"禁言失败: {e}")

    async def get_nickname(self, event: AiocqhttpMessageEvent, user_id: str) -> str:
        from .utils import get_nickname
        return await get_nickname(event, user_id)