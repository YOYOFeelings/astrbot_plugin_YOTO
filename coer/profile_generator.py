import os
import time
import aiohttp
from io import BytesIO
from pathlib import Path
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from astrbot.api import logger

class ProfileImageGenerator:
    def __init__(self, plugin_dir: str, data_dir: str, bg_file: str, font_file: str, blur_radius: int = 2):
        self.plugin_dir = plugin_dir
        self.data_dir = data_dir
        self.bg_path = os.path.join(plugin_dir, 'assets', bg_file)
        self.font_path = os.path.join(plugin_dir, 'assets', font_file)
        self.bg_size = (1640, 856)
        self.blur_radius = blur_radius

        # 头像缓存目录
        self.avatar_cache_dir = Path(data_dir) / "avatar_cache"
        self.avatar_cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_expire = 7 * 24 * 3600

    def _load_font(self, size: int):
        try:
            if os.path.exists(self.font_path):
                return ImageFont.truetype(self.font_path, size)
        except:
            pass
        return ImageFont.load_default()

    async def _download_avatar(self, user_id: str) -> Optional[BytesIO]:
        cache_file = self.avatar_cache_dir / f"{user_id}.jpg"
        if cache_file.exists():
            mtime = cache_file.stat().st_mtime
            if time.time() - mtime < self.cache_expire:
                try:
                    return BytesIO(cache_file.read_bytes())
                except Exception as e:
                    logger.warning(f"读取缓存头像失败: {e}，将重新下载")

        url = f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        cache_file.write_bytes(data)
                        return BytesIO(data)
                    else:
                        logger.error(f"下载头像失败，HTTP {resp.status}")
        except Exception as e:
            logger.error(f"下载头像异常: {e}")

        if cache_file.exists():
            logger.warning(f"头像下载失败，使用过期缓存: {user_id}")
            return BytesIO(cache_file.read_bytes())
        return None

    async def _get_daily_quote(self, config) -> str:
        if config.quote_source == "固定文本":
            return config.fixed_quote if config.fixed_quote else "✨ 今日份的寄语 ✨"
        else:
            try:
                headers = {"Accept-Encoding": "gzip, deflate"}
                async with aiohttp.ClientSession() as session:
                    async with session.get(config.api_url, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            path = config.api_json_path.split('.')
                            value = data
                            for key in path:
                                if isinstance(value, dict):
                                    value = value.get(key, "")
                                else:
                                    value = ""
                                    break
                            if value:
                                return str(value)
                        else:
                            logger.error(f"一言API返回 {resp.status}")
            except Exception as e:
                logger.error(f"获取一言API异常: {e}")
            return "✨ 今日份的寄语 ✨"

    async def create_profile_image(
        self,
        user_id: str,
        nickname: str,
        points: int,
        sign_count: int,
        items: List[Tuple[str, int]],
        rank_info: dict,
        config
    ) -> Optional[str]:
        if not os.path.exists(self.bg_path):
            logger.error(f"背景图不存在: {self.bg_path}")
            return None

        try:
            bg = Image.open(self.bg_path).convert("RGBA").resize(self.bg_size)
            if self.blur_radius > 0:
                bg = bg.filter(ImageFilter.GaussianBlur(radius=self.blur_radius))
            draw = ImageDraw.Draw(bg)

            font_large = self._load_font(48)
            font_medium = self._load_font(36)
            font_small = self._load_font(28)
            rank_title_font = self._load_font(32)
            rank_item_font = self._load_font(28)

            title_color = config.title_color
            text_color = config.text_color

            daily_quote = await self._get_daily_quote(config)

            avatar_io = await self._download_avatar(user_id)
            if avatar_io:
                avatar = Image.open(avatar_io).convert("RGBA")
                avatar_size = (200, 200)
                avatar = avatar.resize(avatar_size)
                mask = Image.new("L", avatar_size, 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0, avatar_size[0], avatar_size[1]), fill=255)
                avatar.putalpha(mask)
            else:
                avatar = None

            # 计算整个内容块的高度
            avatar_height = 200
            name_height = 48 + 36 + 20
            info_height = 36 + 36 + 36 + 50*2
            rank_height = 40 + 28 + 20
            quote_height = 40
            spacing = 40

            total_content_height = avatar_height + name_height + info_height + rank_height + quote_height + spacing*5
            start_y = (self.bg_size[1] - total_content_height) // 2
            y = start_y

            # 绘制头像
            if avatar:
                bg.paste(avatar, (80, y), avatar)
            else:
                draw.ellipse((80, y, 280, y+200), fill=(200,200,200))
            avatar_x, avatar_y = 80, y

            # 昵称和QQ
            name_x = avatar_x + 220
            name_y = avatar_y + 60
            draw.text((name_x, name_y), nickname, font=font_large, fill=title_color)
            qq_text = f"QQ：{user_id}"
            draw.text((name_x, name_y + 60), qq_text, font=font_medium, fill=text_color)

            y += avatar_height + spacing

            # 积分、商品、签到
            line_spacing = 50
            draw.text((80, y), f"💰 积分：{points}", font=font_medium, fill=text_color)
            if items:
                item_text = "🛒 拥有：" + " ".join([f"{name}×{qty}" for name, qty in items])
                draw.text((80, y + line_spacing), item_text, font=font_small, fill=text_color)
            else:
                draw.text((80, y + line_spacing), "🛒 暂无购买记录", font=font_small, fill=text_color)
            draw.text((80, y + 2*line_spacing), f"📅 签到次数：{sign_count}", font=font_medium, fill=text_color)

            y += 2*line_spacing + 36 + spacing

            # 排行榜
            rank_width = 400
            rank_x_positions = [80, 80 + rank_width, 80 + 2*rank_width]
            draw.text((rank_x_positions[0], y), "🏆 积分榜", font=rank_title_font, fill=title_color)
            rank_points = rank_info.get("points_rank", "未上榜")
            draw.text((rank_x_positions[0], y + 40), f"第 {rank_points} 名", font=rank_item_font, fill=text_color)

            draw.text((rank_x_positions[1], y), "📅 签到榜", font=rank_title_font, fill=title_color)
            rank_sign = rank_info.get("sign_rank", "未上榜")
            draw.text((rank_x_positions[1], y + 40), f"第 {rank_sign} 名", font=rank_item_font, fill=text_color)

            draw.text((rank_x_positions[2], y), "🃏 使用榜", font=rank_title_font, fill=title_color)
            rank_use = rank_info.get("use_rank", "未上榜")
            draw.text((rank_x_positions[2], y + 40), f"第 {rank_use} 名", font=rank_item_font, fill=text_color)

            y += 40 + 28 + spacing

            # 每日一言
            bbox = draw.textbbox((0,0), daily_quote, font=font_medium)
            quote_w = bbox[2] - bbox[0]
            draw.text(((self.bg_size[0] - quote_w)/2, y), daily_quote, font=font_medium, fill=text_color)

            temp_dir = os.path.join(self.data_dir, "temp")
            os.makedirs(temp_dir, exist_ok=True)
            out_path = os.path.join(temp_dir, f"profile_{user_id}_{int(time.time())}.png")
            bg.save(out_path)
            return out_path

        except Exception as e:
            logger.error(f"生成个人信息图片失败: {e}")
            return None