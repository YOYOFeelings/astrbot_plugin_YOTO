import time
import random
from datetime import datetime
from typing import Tuple

class SignManager:
    def __init__(self, db, config):
        self.db = db
        self.config = config
        self._daily_special_types = ["幸运数字", "幸运颜色", "今日宜", "幸运方位", "幸运时间"]

    def _get_daily_special(self) -> str:
        t = random.choice(self._daily_special_types)
        if t == "幸运数字":
            num = random.randint(1, 100)
            return f"✨ 今日幸运数字：{num}"
        elif t == "幸运颜色":
            color = random.choice(["红", "橙", "黄", "绿", "青", "蓝", "紫", "粉", "白", "黑"])
            return f"🎨 今日幸运颜色：{color}"
        elif t == "今日宜":
            action = random.choice(["聊天", "潜水", "爆照", "抢红包", "复读", "禁言", "签到"])
            return f"📅 今日宜：{action}"
        elif t == "幸运方位":
            direction = random.choice(["东", "南", "西", "北", "东南", "西南", "东北", "西北"])
            return f"🧭 今日幸运方位：{direction}"
        else:
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            return f"⏰ 今日幸运时间：{hour:02d}:{minute:02d}"

    async def process(self, group_id: str, user_id: str) -> Tuple[bool, str, int]:
        if not self.config.enable_sign:
            return False, "签到功能已关闭", 0

        now = int(time.time())
        user = self.db.get_user(group_id, user_id)
        last = user.get("last_sign_time", 0)

        sign_mode = self.config.sign_mode
        if sign_mode == "24小时制":
            interval = self.config.sign_interval * 3600
            if last > 0 and now - last < interval:
                next_time = last + interval
                return False, f"你已签到过了，下次签到时间：{datetime.fromtimestamp(next_time).strftime('%Y-%m-%d %H:%M:%S')}", 0
        else:
            if last > 0:
                last_date = datetime.fromtimestamp(last).strftime("%Y-%m-%d")
                today = datetime.now().strftime("%Y-%m-%d")
                if last_date == today:
                    return False, "你今天已经签到过了，明天再来吧~", 0

        if self.config.points_type == "固定值":
            points_gain = self.config.fixed_points
        else:
            points_gain = random.randint(self.config.random_min, self.config.random_max)

        interval = self.config.sign_interval * 3600 if sign_mode == "24小时制" else 48 * 3600
        continuous = user.get("continuous_days", 0)
        if last > 0 and now - last < interval * 2:
            continuous += 1
        else:
            continuous = 1

        bonus_days = [int(x.strip()) for x in self.config.continuous_bonus.split(",") if x.strip()]
        bonus_points = 1 if continuous in bonus_days else 0
        total_gain = points_gain + bonus_points

        new_points = user.get("points", 0) + total_gain
        self.db.update_user(
            group_id,
            user_id,
            points=new_points,
            sign_count=user.get("sign_count", 0) + 1,
            last_sign_time=now,
            continuous_days=continuous
        )

        daily_special = self._get_daily_special()

        msg = (
            f"✅ 签到成功！\n"
            f"获得积分：{total_gain}（基础{points_gain}，连续奖励{bonus_points}）\n"
            f"当前积分：{new_points}\n"
            f"累计签到：{user.get('sign_count',0)+1}天\n"
            f"连续签到：{continuous}天\n"
            f"{daily_special}"
        )
        return True, msg, total_gain