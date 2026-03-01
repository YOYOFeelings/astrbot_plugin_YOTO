# coer/config.py
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
    enable_recall: bool = True
    recall_max_count: int = 10
    enable_curfew: bool = False

    # 视频解析设置
    enable_video_parse: bool = True
    video_parse_api_base: str = "https://api.bugpk.com/api"  # 固定 API 地址
    video_send_mode: str = "分开发送"  # 发送方式：分开发送 或 合并转发

    # 宵禁默认时间
    curfew_default_start: str = "23:00"
    curfew_default_end: str = "06:00"

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
    menu_title: str = "感情不是感"
    menu_extra_center: str = ""

    # 签到
    enable_sign: bool = True
    sign_mode: str = "日期制"
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

    # 命令前缀
    command_prefix: str = ""

    # 自定义语录
    ban_me_quotes: List[str] = field(default_factory=lambda: [
        "你已经被禁言了，好好反省一下吧~",
        "禁言已生效，休息一下吧！",
        "你被禁言了，想想自己做错了什么~",
    ])

    # 宵禁数据文件
    curfew_file: Path = field(default_factory=lambda: Path("data/curfew.json"))

    @classmethod
    def from_dict(cls, config: Dict[str, Any], plugin_dir: Path, data_dir: Path) -> "PluginConfig":
        inst = cls(plugin_dir=plugin_dir, data_dir=data_dir)

        if "admin" in config:
            admin = config["admin"]
            # 处理 admin_qq：兼容字符串（逗号分隔）和列表两种格式
            admin_qq_raw = admin.get("admin_qq", "")
            if isinstance(admin_qq_raw, str):
                inst.admin_qqs = [qq.strip() for qq in admin_qq_raw.split(",") if qq.strip()]
            elif isinstance(admin_qq_raw, list):
                inst.admin_qqs = [str(qq).strip() for qq in admin_qq_raw if str(qq).strip()]
            else:
                inst.admin_qqs = []

            inst.group_whitelist = admin.get("group_whitelist", [])
        else:
            inst.group_whitelist = []

        if "features" in config:
            feat = config["features"]
            inst.enable_mute_all = feat.get("enable_mute_all", True)
            inst.enable_ban = feat.get("enable_ban", True)
            inst.enable_kick = feat.get("enable_kick", True)
            inst.enable_block = feat.get("enable_block", True)
            inst.enable_recall = feat.get("enable_recall", True)
            inst.recall_max_count = feat.get("recall_max_count", 10)

        # 宵禁配置独立读取（兼容用户新配置结构）
        if "curfew" in config:
            cur = config["curfew"]
            inst.enable_curfew = cur.get("enable", False)
            inst.curfew_default_start = cur.get("default_start", "23:00")
            inst.curfew_default_end = cur.get("default_end", "06:00")

        # 视频解析配置
        if "video_parse" in config:
            vp = config["video_parse"]
            inst.enable_video_parse = vp.get("enable_video_parse", True)
            inst.video_parse_api_base = vp.get("api_base", "https://api.bugpk.com/api")
            inst.video_send_mode = vp.get("video_send_mode", "分开发送")

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
            inst.menu_title = disp.get("menu_title", "感情不是感")
            inst.menu_extra_center = disp.get("menu_extra_center", "")

        if "sign" in config:
            s = config["sign"]
            inst.enable_sign = s.get("enable_sign", True)
            inst.sign_mode = s.get("sign_mode", "日期制")
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

        if "command" in config:
            inst.command_prefix = config["command"].get("command_prefix", "")

        if "messages" in config and "ban_me_quotes" in config["messages"]:
            quotes = config["messages"]["ban_me_quotes"]
            if isinstance(quotes, str):
                inst.ban_me_quotes = [q.strip() for q in quotes.split("\n") if q.strip()]
            elif isinstance(quotes, list):
                inst.ban_me_quotes = quotes

        inst.curfew_file = data_dir / "curfew.json"
        return inst