# coer/anti_spam.py
import time
from collections import defaultdict, deque
from astrbot.api import logger
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
from .utils import get_nickname  # 新增导入，用于获取用户昵称

class AntiSpam:
    def __init__(self, db, config):
        self.db = db
        self.config = config
        self.msg_timestamps = defaultdict(lambda: defaultdict(lambda: deque(maxlen=config.spam_count)))
        self.last_banned = defaultdict(lambda: defaultdict(float))

    async def check(self, event: AiocqhttpMessageEvent):
        """检查刷屏行为，如果满足条件则执行禁言"""
        if not self.config.enable_spam_detect or self.config.spam_ban_time <= 0:
            return
        group_id = event.get_group_id()
        user_id = event.get_sender_id()
        now = time.time()

        # 如果用户当前处于禁言惩罚期间，直接忽略新消息
        if now - self.last_banned[group_id][user_id] < self.config.spam_ban_time:
            return

        deq = self.msg_timestamps[group_id][user_id]
        deq.append(now)

        # 如果消息数量不足，继续收集
        if len(deq) < self.config.spam_count:
            return

        # 检查最近的 spam_count 条消息的时间间隔
        recent = list(deq)[-self.config.spam_count:]
        intervals = [recent[i+1] - recent[i] for i in range(self.config.spam_count-1)]
        if all(i < self.config.spam_interval for i in intervals):
            # 检测到刷屏，立即标记禁止再次检测
            self.last_banned[group_id][user_id] = now
            await self.apply_ban(event, user_id, group_id, self.config.spam_ban_time, "刷屏", recent)

    async def apply_ban(self, event: AiocqhttpMessageEvent, user_id: str, group_id: str,
                        duration: int, reason: str, recent_timestamps: list = None):
        """
        执行禁言操作，并发送提示信息
        :param recent_timestamps: 最近几条消息的时间戳列表，用于计算实际间隔
        """
        try:
            await event.bot.set_group_ban(group_id=int(group_id), user_id=int(user_id), duration=duration)
            start = int(time.time())
            end = start + duration
            self.db.add_mute_record(user_id, group_id, "bot", reason, duration, start, end)

            # 计算实际的消息间隔和消息数量（用于提示）
            if recent_timestamps and len(recent_timestamps) >= 2:
                first_time = recent_timestamps[0]
                last_time = recent_timestamps[-1]
                total_interval = last_time - first_time
                msg_count = len(recent_timestamps)
                # 格式化间隔，保留一位小数
                interval_str = f"{total_interval:.1f}" if total_interval < 10 else f"{int(total_interval)}"
            else:
                msg_count = self.config.spam_count
                interval_str = f"{self.config.spam_interval * (self.config.spam_count - 1):.1f}"

            # 格式化禁言时长
            minutes = duration // 60
            seconds = duration % 60
            if minutes > 0:
                duration_str = f"{minutes}分钟"
                if seconds > 0:
                    duration_str += f"{seconds}秒"
            else:
                duration_str = f"{seconds}秒"

            # 获取用户昵称
            nickname = await get_nickname(event, user_id)

            # 发送自定义格式的提示
            await event.send(event.plain_result(
                f"检测到刷屏行为\n"
                f"用户：{nickname}({user_id})\n"
                f"在{interval_str}秒内发送了{msg_count}条消息\n"
                f"已被禁言{duration_str}"
            ))
        except Exception as e:
            logger.error(f"禁言失败: {e}")
            # 如果禁言失败，移除禁言标记，允许后续再次检测
            self.last_banned[group_id][user_id] = 0

    async def get_nickname(self, event: AiocqhttpMessageEvent, user_id: str) -> str:
        from .utils import get_nickname
        return await get_nickname(event, user_id)
