from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass, field

@dataclass
class PluginConfig:
    plugin_dir: Path
    data_dir: Path

    # 管理员
    admin_qqs: List[str] = field(default_factory=list)
    group_whitelist: List[str] = field(default_factory=list)

    # 功能开关
    enable_mute_all: bool = True
    enable_ban: bool = True
    enable_kick: bool = True
    enable_block: bool = True

    # 显示
    menu_style: str = "图片"
    sign_style: str = "图片"
    rank_style: str = "图片"
    profile_style: str = "图片"
    profile_blur_radius: int = 2
    rank_blur_radius: int = 2
    menu_blur_radius: int = 2
    title_color: str = "#000000"
    text_color: str = "#000000"
    background_image: str = "Basemap.png"
    font_file: str = "LXGWWenKai-Medium.ttf"
    menu_title: str = "登皮bot"
    menu_extra_center: str = "点赞系统"

    # 签到
    enable_sign: bool = True
    sign_mode: str = "24小时制"
    sign_interval: int = 24
    points_type: str = "固定值"
    fixed_points: int = 1
    random_min: int = 1
    random_max: int = 5
    continuous_bonus: str = ""

    # 刷屏
    enable_spam_detect: bool = True
    spam_count: int = 5
    spam_interval: float = 0.5
    spam_ban_time: int = 600

    # 排行榜
    enable_rank: bool = True
    points_rank_title: str = "🏆 积分排行榜"
    sign_rank_title: str = "📅 签到排行榜"
    use_rank_title: str = "🃏 免禁言卡使用榜"
    rank_max_lines: int = 15

    # 每日一言
    quote_source: str = "固定文本"
    fixed_quote: str = "今天也是元气满满的一天！"
    api_url: str = "https://v1.hitokoto.cn/"
    api_json_path: str = "hitokoto"

    # 小姐姐视频（简化版）
    enable_girl_video: bool = False
    girl_video_api_url: str = "https://v2.xxapi.cn/api/meinv"
    girl_video_download_video: bool = True
    girl_video_send_as_forward: bool = False

    # 命令前缀
    command_prefix: str = ""

    # 自定义语录
    ban_me_quotes: List[str] = field(default_factory=lambda: [
        "你已经被禁言了，好好反省一下吧~",
        "禁言已生效，休息一下吧！",
        "你被禁言了，想想自己做错了什么~",
    ])

    @classmethod
    def from_dict(cls, config: Dict[str, Any], plugin_dir: Path, data_dir: Path) -> "PluginConfig":
        inst = cls(plugin_dir=plugin_dir, data_dir=data_dir)

        if "admin" in config:
            admin = config["admin"]
            admin_qq_str = admin.get("admin_qq", "")
            inst.admin_qqs = [qq.strip() for qq in admin_qq_str.split(",") if qq.strip()]
            inst.group_whitelist = admin.get("group_whitelist", [])
        else:
            inst.group_whitelist = []

        if "features" in config:
            feat = config["features"]
            inst.enable_mute_all = feat.get("enable_mute_all", True)
            inst.enable_ban = feat.get("enable_ban", True)
            inst.enable_kick = feat.get("enable_kick", True)
            inst.enable_block = feat.get("enable_block", True)

        if "display" in config:
            disp = config["display"]
            inst.menu_style = disp.get("menu_style", "图片")
            inst.sign_style = disp.get("sign_style", "图片")
            inst.rank_style = disp.get("rank_style", "图片")
            inst.profile_style = disp.get("profile_style", "图片")
            inst.profile_blur_radius = disp.get("profile_blur_radius", 2)
            inst.rank_blur_radius = disp.get("rank_blur_radius", 2)
            inst.menu_blur_radius = disp.get("menu_blur_radius", 2)
            inst.title_color = disp.get("title_color", "#000000")
            inst.text_color = disp.get("text_color", "#000000")
            inst.background_image = disp.get("background_image", "Basemap.png")
            inst.font_file = disp.get("font_file", "LXGWWenKai-Medium.ttf")
            inst.menu_title = disp.get("menu_title", "登皮bot")
            inst.menu_extra_center = disp.get("menu_extra_center", "点赞系统")

        if "sign" in config:
            s = config["sign"]
            inst.enable_sign = s.get("enable_sign", True)
            inst.sign_mode = s.get("sign_mode", "24小时制")
            inst.sign_interval = s.get("sign_interval", 24)
            inst.points_type = s.get("points_type", "固定值")
            inst.fixed_points = s.get("fixed_points", 1)
            inst.random_min = s.get("random_min", 1)
            inst.random_max = s.get("random_max", 5)
            inst.continuous_bonus = s.get("continuous_bonus", "")

        if "spam" in config:
            sp = config["spam"]
            inst.enable_spam_detect = sp.get("enable_spam_detect", True)
            inst.spam_count = sp.get("spam_count", 5)
            inst.spam_interval = sp.get("spam_interval", 0.5)
            inst.spam_ban_time = sp.get("spam_ban_time", 600)

        if "rank" in config:
            r = config["rank"]
            inst.enable_rank = r.get("enable_rank", True)
            inst.points_rank_title = r.get("points_rank_title", "🏆 积分排行榜")
            inst.sign_rank_title = r.get("sign_rank_title", "📅 签到排行榜")
            inst.use_rank_title = r.get("use_rank_title", "🃏 免禁言卡使用榜")
            inst.rank_max_lines = r.get("rank_max_lines", 15)

        if "daily_quote" in config:
            dq = config["daily_quote"]
            inst.quote_source = dq.get("quote_source", "固定文本")
            inst.fixed_quote = dq.get("fixed_quote", "今天也是元气满满的一天！")
            inst.api_url = dq.get("api_url", "https://v1.hitokoto.cn/")
            inst.api_json_path = dq.get("api_json_path", "hitokoto")

        if "girl_video" in config:
            gv = config["girl_video"]
            inst.enable_girl_video = gv.get("enable", False)
            inst.girl_video_api_url = gv.get("api_url", "https://v2.xxapi.cn/api/meinv")
            inst.girl_video_download_video = gv.get("download_video", True)
            inst.girl_video_send_as_forward = gv.get("send_as_forward", False)

        if "command" in config:
            inst.command_prefix = config["command"].get("command_prefix", "")

        if "messages" in config and "ban_me_quotes" in config["messages"]:
            quotes = config["messages"]["ban_me_quotes"]
            if isinstance(quotes, str):
                inst.ban_me_quotes = [q.strip() for q in quotes.split("\n") if q.strip()]
            elif isinstance(quotes, list):
                inst.ban_me_quotes = quotes

        return inst