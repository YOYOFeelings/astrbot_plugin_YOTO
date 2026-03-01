import asyncio
import aiohttp
from typing import Optional, Dict

async def parse_weibo(url: str, cookies: dict = None) -> Optional[Dict]:
    """
    调用外部API解析微博
    :param url: 微博分享链接
    :param cookies: 外部API不需要cookies，保留参数以保持接口一致
    :return: 统一格式的字典
    """
    try:
        api_base = "https://api.bugpk.com/api/weibo"
        print(f"[微博] 请求API: {api_base} 参数: {url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_base, params={'url': url}, timeout=15) as resp:
                if resp.status != 200:
                    print(f"[微博] API请求失败，HTTP {resp.status}")
                    return None
                data = await resp.json()
                if data.get('code') != 200:
                    print(f"[微博] API返回错误: {data.get('msg')}")
                    return None
                api_data = data.get('data')
                if not api_data:
                    print("[微博] API返回数据为空")
                    return None

                # 判断类型
                type_val = api_data.get('type')
                if type_val == 1 or type_val == '1' or type_val == 'video':
                    type_str = '1'
                elif type_val == 2 or type_val == '2' or type_val == 'image':
                    type_str = '2'
                else:
                    type_str = str(type_val) if type_val else 'unknown'

                # 提取作者信息（假设微博返回格式与抖音类似）
                author_name = '未知作者'
                author_avatar = ''
                author_obj = api_data.get('author')
                if isinstance(author_obj, dict):
                    author_name = author_obj.get('name') or author_obj.get('nickname') or '未知作者'
                    author_avatar = author_obj.get('avatar') or ''
                # 如果没有author对象，尝试直接获取nickName
                if author_name == '未知作者':
                    author_name = api_data.get('nickName') or '未知作者'
                if not author_avatar:
                    author_avatar = api_data.get('avatar') or ''

                unified = {
                    'title': api_data.get('title', ''),
                    'cover': api_data.get('cover', ''),
                    'author': {
                        'name': author_name,
                        'avatar': author_avatar
                    },
                    'platform': 'weibo',
                    'type': type_str,
                    'url': api_data.get('videoUrl') or api_data.get('url', ''),
                    'video_backup': api_data.get('video_backup', []),
                    'imageList': api_data.get('images', []),
                    'live_photo': api_data.get('live_photo', [])
                }
                print(f"[微博] 解析成功: {unified}")
                return unified
    except Exception as e:
        print(f"[微博] 解析异常: {e}")
        return None