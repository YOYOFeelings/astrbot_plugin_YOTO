import aiohttp
from typing import Optional
from astrbot.api import logger

class GirlVideoManager:
    def __init__(self, config):
        """
        :param config: 插件配置对象（PluginConfig 实例）
        """
        self.config = config

    async def get_video_url(self) -> Optional[str]:
        """根据配置获取视频URL（假设API直接返回纯文本URL）"""
        if not self.config.enable_girl_video:
            return None

        api_url = self.config.girl_video_api_url
        if not api_url:
            logger.error("小姐姐视频API地址为空")
            return None

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(api_url, timeout=15) as resp:
                    if resp.status != 200:
                        logger.error(f"小姐姐视频API返回非200状态码: {resp.status}")
                        return None
                    # 假设API直接返回视频URL（纯文本）
                    video_url = await resp.text()
                    return video_url.strip()
            except Exception as e:
                logger.error(f"调用小姐姐视频API失败: {e}")
                return None