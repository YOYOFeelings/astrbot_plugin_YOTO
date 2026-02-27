import sqlite3
import json
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime
from astrbot.api import logger

class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # 检查是否需要迁移
            cursor = conn.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            if "group_id" not in columns:
                logger.warning("检测到数据库需要迁移以支持群隔离，正在进行自动迁移...")
                conn.execute("ALTER TABLE users RENAME TO users_old")
                conn.execute("""
                    CREATE TABLE users (
                        group_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        points INTEGER DEFAULT 0,
                        sign_count INTEGER DEFAULT 0,
                        last_sign_time INTEGER DEFAULT 0,
                        continuous_days INTEGER DEFAULT 0,
                        immunity_cards INTEGER DEFAULT 0,
                        PRIMARY KEY (group_id, user_id)
                    )
                """)
                conn.execute("""
                    INSERT INTO users (group_id, user_id, points, sign_count, last_sign_time, continuous_days, immunity_cards)
                    SELECT '0', user_id, points, sign_count, last_sign_time, continuous_days, immunity_cards FROM users_old
                """)
                conn.execute("DROP TABLE users_old")
                logger.info("数据库迁移完成，旧数据已放入群ID '0'，请根据需要调整。")
            else:
                pass

            conn.execute("""
                CREATE TABLE IF NOT EXISTS shop_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    price INTEGER NOT NULL,
                    daily_limit INTEGER DEFAULT 0,
                    total_limit INTEGER DEFAULT 0,
                    sold_today INTEGER DEFAULT 0,
                    sold_total INTEGER DEFAULT 0,
                    last_reset_day TEXT,
                    data TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    item_id INTEGER NOT NULL,
                    quantity INTEGER DEFAULT 1,
                    purchase_time INTEGER NOT NULL,
                    used BOOLEAN DEFAULT 0,
                    used_time INTEGER
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mutes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    group_id TEXT NOT NULL,
                    operator TEXT,
                    reason TEXT,
                    duration INTEGER,
                    start_time INTEGER,
                    end_time INTEGER
                )
            """)
            conn.commit()

    # ---------- 用户相关 ----------
    def get_user(self, group_id: str, user_id: str) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM users WHERE group_id = ? AND user_id = ?", (group_id, user_id))
            row = cur.fetchone()
            if row:
                return dict(row)
            else:
                conn.execute("INSERT INTO users (group_id, user_id) VALUES (?, ?)", (group_id, user_id))
                conn.commit()
                return {"group_id": group_id, "user_id": user_id, "points": 0, "sign_count": 0,
                        "last_sign_time": 0, "continuous_days": 0, "immunity_cards": 0}

    def update_user(self, group_id: str, user_id: str, **kwargs):
        fields = ", ".join([f"{k}=?" for k in kwargs])
        values = list(kwargs.values()) + [group_id, user_id]
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"UPDATE users SET {fields} WHERE group_id=? AND user_id=?", values)
            conn.commit()

    def add_points(self, group_id: str, user_id: str, points: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE users SET points = points + ? WHERE group_id=? AND user_id=?", (points, group_id, user_id))
            conn.commit()

    # ---------- 商品相关（未使用，保留） ----------
    def get_shop_items(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM shop_items ORDER BY id")
            return [dict(row) for row in cur.fetchall()]

    def get_item(self, item_id: int) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM shop_items WHERE id=?", (item_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def add_item(self, name: str, price: int, description: str = "",
                 daily_limit: int = 0, total_limit: int = 0, data: str = "{}"):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO shop_items (name, description, price, daily_limit, total_limit, data) VALUES (?,?,?,?,?,?)",
                (name, description, price, daily_limit, total_limit, data)
            )
            conn.commit()

    def update_item(self, item_id: int, **kwargs):
        fields = ", ".join([f"{k}=?" for k in kwargs])
        values = list(kwargs.values()) + [item_id]
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"UPDATE shop_items SET {fields} WHERE id=?", values)
            conn.commit()

    def delete_item(self, item_id: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM shop_items WHERE id=?", (item_id,))
            conn.commit()

    def reset_daily_limits(self):
        today = datetime.now().strftime("%Y-%m-%d")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE shop_items SET sold_today = 0 WHERE last_reset_day != ? OR last_reset_day IS NULL", (today,))
            conn.execute("UPDATE shop_items SET last_reset_day = ?", (today,))
            conn.commit()

    # ---------- 购买记录 ----------
    def add_purchase(self, user_id: str, item_id: int, quantity: int = 1) -> int:
        now = int(datetime.now().timestamp())
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO purchases (user_id, item_id, quantity, purchase_time) VALUES (?,?,?,?)",
                (user_id, item_id, quantity, now)
            )
            conn.commit()
            return cur.lastrowid

    def get_user_purchases(self, user_id: str, item_id: Optional[int] = None) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if item_id:
                cur = conn.execute(
                    "SELECT * FROM purchases WHERE user_id=? AND item_id=? ORDER BY purchase_time DESC",
                    (user_id, item_id)
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM purchases WHERE user_id=? ORDER BY purchase_time DESC",
                    (user_id,)
                )
            return [dict(row) for row in cur.fetchall()]

    def mark_card_used(self, purchase_id: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE purchases SET used=1, used_time=? WHERE id=?",
                (int(datetime.now().timestamp()), purchase_id)
            )
            conn.commit()

    # ---------- 禁言记录 ----------
    def add_mute_record(self, user_id: str, group_id: str, operator: str, reason: str,
                        duration: int, start_time: int, end_time: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO mutes (user_id, group_id, operator, reason, duration, start_time, end_time) VALUES (?,?,?,?,?,?,?)",
                (user_id, group_id, operator, reason, duration, start_time, end_time)
            )
            conn.commit()

    def get_latest_mute(self, user_id: str, group_id: Optional[str] = None) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if group_id:
                cur = conn.execute(
                    "SELECT * FROM mutes WHERE user_id=? AND group_id=? ORDER BY start_time DESC LIMIT 1",
                    (user_id, group_id)
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM mutes WHERE user_id=? ORDER BY start_time DESC LIMIT 1",
                    (user_id,)
                )
            row = cur.fetchone()
            return dict(row) if row else None

    # ---------- 排行榜（群隔离） ----------
    def get_points_rank(self, group_id: str, limit: int = 20) -> List[Tuple[str, int]]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT user_id, points FROM users WHERE group_id=? ORDER BY points DESC LIMIT ?",
                (group_id, limit)
            )
            return cur.fetchall()

    def get_sign_rank(self, group_id: str, limit: int = 20) -> List[Tuple[str, int]]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT user_id, sign_count FROM users WHERE group_id=? ORDER BY sign_count DESC LIMIT ?",
                (group_id, limit)
            )
            return cur.fetchall()

    def get_card_usage_rank(self, group_id: str, limit: int = 20) -> List[Tuple[str, int]]:
        # 由于免禁言卡已移除，此方法保留但始终返回空列表
        return []