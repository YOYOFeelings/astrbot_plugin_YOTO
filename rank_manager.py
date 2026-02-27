import os
import time
from typing import List
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from astrbot.api import logger

class RankImageGenerator:
    def __init__(self, plugin_dir: str, data_dir: str, bg_file: str, font_file: str):
        self.plugin_dir = plugin_dir
        self.data_dir = data_dir
        self.bg_path = os.path.join(plugin_dir, bg_file)
        self.font_path = os.path.join(plugin_dir, font_file)
        self.bg_size = (1640, 856)

    def _load_font(self, size: int):
        try:
            if os.path.exists(self.font_path):
                return ImageFont.truetype(self.font_path, size)
        except:
            pass
        return ImageFont.load_default()

    async def create_rank_image(self, title: str, lines: List[str], max_lines: int = 15,
                                 blur_radius: int = 0, title_color: str = "#000000", text_color: str = "#000000") -> str:
        if not os.path.exists(self.bg_path):
            logger.error(f"背景图不存在: {self.bg_path}")
            return ""
        try:
            bg = Image.open(self.bg_path).resize(self.bg_size)
            if blur_radius > 0:
                bg = bg.filter(ImageFilter.GaussianBlur(radius=blur_radius))
            draw = ImageDraw.Draw(bg)
            title_font = self._load_font(48)
            text_font = self._load_font(32)

            # 计算标题高度
            title_bbox = draw.textbbox((0, 0), title, font=title_font)
            title_height = title_bbox[3] - title_bbox[1]

            # 计算所有内容行的总高度
            displayed = lines[:max_lines]
            total_height = title_height + 20
            line_heights = []
            for line in displayed:
                bbox = draw.textbbox((0, 0), line, font=text_font)
                line_height = bbox[3] - bbox[1]
                line_heights.append(line_height)
                total_height += line_height + 10
            if len(lines) > max_lines:
                bbox = draw.textbbox((0, 0), f"... 共{len(lines)}人", font=text_font)
                line_height = bbox[3] - bbox[1]
                total_height += line_height + 10

            # 计算起始Y坐标（垂直居中）
            start_y = (self.bg_size[1] - total_height) // 2
            y = start_y

            # 绘制标题（水平居中）
            title_bbox = draw.textbbox((0, 0), title, font=title_font)
            title_w = title_bbox[2] - title_bbox[0]
            draw.text(((self.bg_size[0] - title_w)/2, y), title, font=title_font, fill=title_color)
            y += title_height + 20

            # 绘制内容行
            for i, line in enumerate(displayed):
                draw.text((100, y), line, font=text_font, fill=text_color)
                y += line_heights[i] + 10

            if len(lines) > max_lines:
                draw.text((100, y), f"... 共{len(lines)}人", font=text_font, fill=text_color)

            temp_dir = os.path.join(self.data_dir, "temp")
            os.makedirs(temp_dir, exist_ok=True)
            out_path = os.path.join(temp_dir, f"rank_{int(time.time())}.png")
            bg.save(out_path)
            return out_path
        except Exception as e:
            logger.error(f"生成排行榜图片失败: {e}")
            return ""

    async def create_menu_image(self, title: str, lines: List[str],
                                 blur_radius: int = 0, title_color: str = "#000000", text_color: str = "#000000") -> str:
        if not os.path.exists(self.bg_path):
            logger.error(f"背景图不存在: {self.bg_path}")
            return ""
        try:
            bg = Image.open(self.bg_path).resize(self.bg_size)
            if blur_radius > 0:
                bg = bg.filter(ImageFilter.GaussianBlur(radius=blur_radius))
            draw = ImageDraw.Draw(bg)
            title_font = self._load_font(48)
            text_font = self._load_font(28)

            # 计算标题高度
            title_bbox = draw.textbbox((0, 0), title, font=title_font)
            title_height = title_bbox[3] - title_bbox[1]

            # 计算所有内容行的总高度
            total_height = title_height + 20
            line_heights = []
            for line in lines:
                if line.strip():
                    bbox = draw.textbbox((0, 0), line, font=text_font)
                    line_height = bbox[3] - bbox[1]
                    line_heights.append(line_height)
                    total_height += line_height + 10
                else:
                    line_heights.append(20)
                    total_height += 20 + 10

            # 计算起始Y坐标（垂直居中）
            start_y = (self.bg_size[1] - total_height) // 2
            y = start_y

            # 绘制标题（水平居中）
            title_bbox = draw.textbbox((0, 0), title, font=title_font)
            title_w = title_bbox[2] - title_bbox[0]
            draw.text(((self.bg_size[0] - title_w)/2, y), title, font=title_font, fill=title_color)
            y += title_height + 20

            # 绘制内容行（水平居中）
            for i, line in enumerate(lines):
                if line.strip():
                    bbox = draw.textbbox((0, 0), line, font=text_font)
                    text_w = bbox[2] - bbox[0]
                    x = (self.bg_size[0] - text_w) / 2
                    draw.text((x, y), line, font=text_font, fill=text_color)
                y += line_heights[i] + 10

            temp_dir = os.path.join(self.data_dir, "temp")
            os.makedirs(temp_dir, exist_ok=True)
            out_path = os.path.join(temp_dir, f"menu_{int(time.time())}.png")
            bg.save(out_path)
            return out_path
        except Exception as e:
            logger.error(f"生成菜单图片失败: {e}")
            return ""