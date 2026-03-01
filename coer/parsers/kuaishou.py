import asyncio
import aiohttp
from typing import Optional, Dict

async def parse_kuaishou(url: str, cookies: dict = None) -> Optional[Dict]:
    """
    调用外部API解析快手
    :param url: 快手分享链接
    :param cookies: 外部API不需要cookies，保留参数以保持接口一致
    :return: 统一格式的字典
    """
    try:
        api_base = "https://api.bugpk.com/api/ksjx"
        print(f"[快手] 请求API: {api_base} 参数: {url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_base, params={'url': url}, timeout=15) as resp:
                print(f"[快手] API响应状态码: {resp.status}")
                
                if resp.status != 200:
                    print(f"[快手] API请求失败，HTTP {resp.status}")
                    return None
                    
                data = await resp.json()
                print(f"[快手] API原始返回数据: {data}")
                
                # 检查API返回状态
                api_data = None
                if data.get('code') == 200:
                    api_data = data.get('data')
                elif data.get('code') is None and data.get('data'):
                    api_data = data.get('data')
                else:
                    api_data = data
                
                if not api_data:
                    print("[快手] API返回数据为空")
                    return None

                # 快手返回示例中没有作者信息，设为默认
                author_name = '未知作者'
                author_avatar = ''

                # 判断类型
                type_val = api_data.get('type')
                if type_val in (1, '1', 'video'):
                    type_str = '1'
                elif type_val in (2, '2', 'image', 'images'):
                    type_str = '2'
                else:
                    # 如果有视频URL，默认为视频类型
                    if api_data.get('videoUrl') or api_data.get('url'):
                        type_str = '1'
                    else:
                        type_str = 'unknown'

                unified = {
                    'title': api_data.get('title', ''),
                    'cover': api_data.get('cover', ''),
                    'author': {
                        'name': author_name,
                        'avatar': author_avatar
                    },
                    'platform': 'kuaishou',
                    'type': type_str,
                    'url': api_data.get('videoUrl') or api_data.get('url', ''),
                    'video_backup': api_data.get('video_backup', []),
                    'imageList': api_data.get('images') or api_data.get('imageList') or [],
                    'live_photo': api_data.get('live_photo', [])
                }
                print(f"[快手] 解析成功: {unified}")
                return unified
                
    except Exception as e:
        print(f"[快手] 解析异常: {e}")
        return None