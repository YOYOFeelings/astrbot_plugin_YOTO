import re
from typing import Optional, Dict

# 导入各个平台的解析器
from .parsers.douyin import parse_douyin
from .parsers.kuaishou import parse_kuaishou
from .parsers.bilibili import parse_bilibili
from .parsers.xiaohongshu import parse_xiaohongshu
from .parsers.weibo import parse_weibo
from .parsers.toutiao import parse_toutiao
from .parsers.pipixia import parse_pipixia

# 平台名称与解析函数的映射
PLATFORM_PARSER_MAP = {
    'douyin': parse_douyin,
    'kuaishou': parse_kuaishou,
    'bilibili': parse_bilibili,
    'xiaohongshu': parse_xiaohongshu,
    'weibo': parse_weibo,
    'toutiao': parse_toutiao,
    'pipixia': parse_pipixia,
}

# 域名到平台名称的映射（用于识别）
DOMAIN_PLATFORM_MAP = {
    'douyin.com': 'douyin',
    'iesdouyin.com': 'douyin',
    'kuaishou.com': 'kuaishou',
    'v.kuaishou.com': 'kuaishou',  # 必须包含
    'kwai.com': 'kuaishou',
    'bilibili.com': 'bilibili',
    'b23.tv': 'bilibili',
    'xiaohongshu.com': 'xiaohongshu',
    'xhslink.com': 'xiaohongshu',
    'weibo.com': 'weibo',
    'toutiao.com': 'toutiao',
    'pipixia.com': 'pipixia'
}

def extract_url(text: str) -> Optional[str]:
    """从文本中提取第一个URL"""
    regex = r'https?://[^\s]+'
    match = re.search(regex, text)
    if match:
        url = match.group(0)
        print(f"[video_parser] 提取到URL: {url}")
        return url
    print("[video_parser] 未找到URL")
    return None

def get_platform(url: str) -> str:
    """根据URL识别平台"""
    url_lower = url.lower()
    for domain, platform in DOMAIN_PLATFORM_MAP.items():
        if domain in url_lower:
            print(f"[video_parser] 域名 {domain} 匹配到平台: {platform}")
            return platform
    print(f"[video_parser] 未匹配到任何平台，URL: {url}")
    return 'unknown'

async def parse_video(input_text: str, cookies: dict = None) -> Dict:
    """
    主解析函数，根据平台调用对应的解析器
    :param input_text: 用户输入，包含链接
    :param cookies: 传递给解析器的cookies（外部API通常不需要）
    :return: 统一格式的字典，包含 success, code, message, data
    """
    print(f"[video_parser] 收到解析请求: {input_text}")
    
    # 提取URL
    url = extract_url(input_text)
    if not url:
        return {
            'success': False,
            'code': 400,
            'message': '未找到有效的视频链接',
            'data': None
        }

    # 识别平台
    platform = get_platform(url)
    if platform == 'unknown':
        return {
            'success': False,
            'code': 400,
            'message': '暂不支持该平台，目前支持：抖音、快手、B站、小红书、微博、今日头条、皮皮虾',
            'data': None
        }

    # 获取对应的解析函数
    parser_func = PLATFORM_PARSER_MAP.get(platform)
    print(f"[video_parser] 平台 {platform} 对应的解析函数: {parser_func}")
    
    if not parser_func:
        return {
            'success': False,
            'code': 400,
            'message': f'平台 {platform} 未配置解析器',
            'data': None
        }

    try:
        # 调用解析器
        print(f"[video_parser] 开始调用 {platform} 解析器，URL: {url}")
        result = await parser_func(url, cookies)
        print(f"[video_parser] 解析器返回结果: {result}")
        
        if not result:
            return {
                'success': False,
                'code': 404,
                'message': '解析失败，请检查链接是否有效',
                'data': None
            }
        return {
            'success': True,
            'code': 200,
            'message': '解析成功',
            'data': result
        }
    except Exception as e:
        print(f"[video_parser] 解析异常: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'code': 500,
            'message': f'解析异常: {str(e)}',
            'data': None
        }