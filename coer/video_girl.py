# coer/video_girl.py
import aiohttp
import json
from typing import Optional
from astrbot.api import logger

class GirlVideoManager:
    def __init__(self, config):
        """
        :param config: 插件配置对象（PluginConfig 实例）
        """
        self.config = config

    async def get_video_url(self) -> Optional[str]:
        """根据配置获取视频URL，尝试多种解析方式"""
        if not self.config.enable_girl_video:
            return None

        api_url = self.config.girl_video_api_url
        if not api_url:
            logger.error("小姐姐视频API地址为空")
            return None

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(api_url, timeout=15, allow_redirects=True) as resp:
                    if resp.status != 200:
                        logger.error(f"小姐姐视频API返回非200状态码: {resp.status}")
                        return None

                    final_url = str(resp.url)
                    if final_url.lower().endswith(('.mp4', '.flv', '.avi', '.mov', '.mkv')):
                        return final_url

                    text = await resp.text()
                    text = text.strip()

                    if text.startswith('http'):
                        return text

                    try:
                        data = json.loads(text)
                        def find_url(obj):
                            if isinstance(obj, dict):
                                for v in obj.values():
                                    result = find_url(v)
                                    if result:
                                        return result
                            elif isinstance(obj, list):
                                for item in obj:
                                    result = find_url(item)
                                    if result:
                                        return result
                            elif isinstance(obj, str) and obj.startswith('http') and any(obj.lower().endswith(ext) for ext in ['.mp4','.flv','.avi','.mov','.mkv']):
                                return obj
                            return None
                        url = find_url(data)
                        if url:
                            return url
                    except json.JSONDecodeError:
                        pass

                    return final_url
            except Exception as e:
                logger.error(f"调用小姐姐视频API失败: {e}")
                return None