import re
import json
import asyncio
import random
from typing import Optional, Dict
import aiohttp
from astrbot.api import logger

async def log_info(msg):
    logger.info(msg)

async def log_error(msg, error=None):
    if error:
        logger.error(f"{msg} {error}")
    else:
        logger.error(msg)

USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
]

def random_ua():
    return random.choice(USER_AGENTS)

async def fetch_text(session, url, headers=None, follow_redirects=True, retries=3):
    for attempt in range(retries):
        try:
            async with session.get(url, headers=headers, allow_redirects=follow_redirects, timeout=15) as resp:
                if resp.status == 200:
                    return await resp.text()
                else:
                    await log_error(f"请求失败 HTTP {resp.status}，重试 {attempt+1}/{retries}")
        except Exception as e:
            await log_error(f"请求异常 {e}，重试 {attempt+1}/{retries}")
        await asyncio.sleep(1 * (attempt + 1))
    return None

async def fetch_json(session, url, headers=None, retries=3):
    for attempt in range(retries):
        try:
            async with session.get(url, headers=headers, timeout=15) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    await log_error(f"JSON请求失败 HTTP {resp.status}，重试 {attempt+1}/{retries}")
        except Exception as e:
            await log_error(f"JSON请求异常 {e}，重试 {attempt+1}/{retries}")
        await asyncio.sleep(1 * (attempt + 1))
    return None

async def fetch_redirect_url(session, url, headers=None):
    try:
        async with session.get(url, headers=headers, allow_redirects=False) as resp:
            if resp.status in (301, 302, 303, 307, 308):
                location = resp.headers.get('Location')
                if location:
                    return location
            return url
    except Exception as e:
        await log_error("获取重定向失败", e)
        return url

def extract_url(text):
    if not text:
        return None
    regex = r'https?://[^\s]+'
    match = re.search(regex, text)
    return match.group(0) if match else None

def get_platform(url):
    url = url.lower()
    domains = {
        'douyin': ['douyin.com', 'iesdouyin.com', 'amemv.com', 'v.douyin.com'],
        'kuaishou': ['kuaishou.com', 'kwaixiaodian.com', 'kwai.com'],
        'bilibili': ['bilibili.com', 'b23.tv'],
        'xiaohongshu': ['xiaohongshu.com']
    }
    for platform, domain_list in domains.items():
        for domain in domain_list:
            if domain in url:
                return platform
    return 'unknown'

async def extract_json_data(html, marker):
    # 构建两种标记形式
    # 形式1: window.xxx = {...};
    pattern1 = re.escape(marker) + r'\s*=\s*({.*?});'
    # 形式2: window["xxx"] = {...};
    # 将 marker 中的 "window." 替换为 "window[\"", 并添加 "\"]"
    if marker.startswith('window.'):
        inner = marker[7:]  # 去掉 'window.'
        alt_marker = 'window["' + inner + '"]'
    else:
        alt_marker = marker
    pattern2 = re.escape(alt_marker) + r'\s*=\s*({.*?});'
    
    for pattern in (pattern1, pattern2):
        match = re.search(pattern, html, re.DOTALL)
        if match:
            json_str = match.group(1)
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            return json_str
    return '{}'

# ---------- 抖音解析 ----------
async def parse_douyin(url):
    try:
        await log_info(f'[抖音] 开始解析: {url}')
        headers = {
            'User-Agent': random_ua(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        async with aiohttp.ClientSession() as session:
            final_url = await fetch_redirect_url(session, url, headers)
            if not final_url:
                raise Exception('重定向失败')
            await log_info(f'[抖音] 最终URL: {final_url}')

            html = await fetch_text(session, final_url, headers)
            if not html:
                raise Exception('页面获取失败')

            json_str = await extract_json_data(html, 'window._ROUTER_DATA')
            if json_str == '{}':
                json_str = await extract_json_data(html, 'window["_ROUTER_DATA"]')
            if json_str != '{}':
                try:
                    json_obj = json.loads(json_str)
                    if json_obj and 'loaderData' in json_obj:
                        loader_data = json_obj['loaderData']
                        page_info = None
                        for key, value in loader_data.items():
                            if ('video_' in key and '/page' in key) or ('note_' in key and '/page' in key):
                                page_info = value
                                break
                        if page_info and 'videoInfoRes' in page_info and 'item_list' in page_info['videoInfoRes']:
                            item = page_info['videoInfoRes']['item_list'][0]
                            result = {}
                            if 'video' in item:
                                video_url = ''
                                if 'play_addr' in item['video'] and 'url_list' in item['video']['play_addr']:
                                    video_url = item['video']['play_addr']['url_list'][0]
                                elif 'playAddr' in item['video'] and 'url_list' in item['video']['playAddr']:
                                    video_url = item['video']['playAddr']['url_list'][0]
                                elif 'playApi' in item['video']:
                                    video_url = item['video']['playApi']
                                if video_url:
                                    video_url = video_url.replace('playwm', 'play').replace('720p', '1080p')
                                    result = {
                                        'title': item.get('desc') or item.get('title') or '无标题',
                                        'nickName': item.get('author', {}).get('nickname') or item.get('author', {}).get('nick_name') or '未知作者',
                                        'type': 1,
                                        'videoUrl': video_url,
                                        'cover': item.get('video', {}).get('cover', {}).get('url_list', [None])[0] or '',
                                        'platform': 'douyin'
                                    }
                            elif 'images' in item:
                                image_list = []
                                for img in item['images']:
                                    if 'url_list' in img and img['url_list']:
                                        image_list.append(img['url_list'][0])
                                if image_list:
                                    result = {
                                        'title': item.get('desc') or item.get('title') or '无标题',
                                        'nickName': item.get('author', {}).get('nickname') or item.get('author', {}).get('nick_name') or '未知作者',
                                        'type': 2,
                                        'imageList': image_list,
                                        'platform': 'douyin'
                                    }
                            if result:
                                await log_info('[抖音] 解析成功（_ROUTER_DATA）')
                                return result
                except json.JSONDecodeError:
                    json_obj = None
                except Exception as e:
                    await log_error('[抖音] JSON解析失败', e)

            # 备选正则匹配
            play_match = re.search(r'"playAddr"\s*:\s*"([^"]+)"', html)
            if play_match:
                video_url = play_match.group(1).replace('\\u002F', '/').replace('\\/', '/')
                title_match = re.search(r'"desc"\s*:\s*"([^"]+)"', html)
                title = title_match.group(1) if title_match else '无标题'
                author_match = re.search(r'"nickname"\s*:\s*"([^"]+)"', html)
                author = author_match.group(1) if author_match else '未知作者'
                cover_match = re.search(r'"cover"\s*:\s*{[^}]*"url_list"\s*:\s*\["([^"]+)"', html)
                cover = cover_match.group(1) if cover_match else ''
                result = {
                    'title': title,
                    'nickName': author,
                    'type': 1,
                    'videoUrl': video_url,
                    'cover': cover,
                    'platform': 'douyin'
                }
                await log_info('[抖音] 解析成功（正则匹配）')
                return result

            img_matches = re.findall(r'"url_list"\s*:\s*\["([^"]+)"', html)
            if len(img_matches) > 1:
                image_list = [u.replace('\\u002F', '/') for u in img_matches]
                title_match = re.search(r'"desc"\s*:\s*"([^"]+)"', html)
                title = title_match.group(1) if title_match else '无标题'
                author_match = re.search(r'"nickname"\s*:\s*"([^"]+)"', html)
                author = author_match.group(1) if author_match else '未知作者'
                result = {
                    'title': title,
                    'nickName': author,
                    'type': 2,
                    'imageList': image_list,
                    'platform': 'douyin'
                }
                await log_info('[抖音] 解析成功（图集正则）')
                return result

            raise Exception('所有解析方法均失败')
    except Exception as e:
        await log_error('[抖音] 解析失败', str(e))
        return None

# ---------- 快手解析 ----------
async def parse_kuaishou(url):
    try:
        await log_info(f'[快手] 开始解析: {url}')
        headers = {
            'User-Agent': random_ua(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        async with aiohttp.ClientSession() as session:
            final_url = await fetch_redirect_url(session, url, headers)
            if not final_url:
                raise Exception('重定向失败')
            await log_info(f'[快手] 最终URL: {final_url}')

            html = await fetch_text(session, final_url, headers)
            if not html:
                raise Exception('页面获取失败')

            json_str = await extract_json_data(html, 'window.INIT_STATE')
            if json_str == '{}':
                json_str = await extract_json_data(html, 'window["INIT_STATE"]')
            if json_str != '{}':
                try:
                    json_obj = json.loads(json_str)
                    if json_obj:
                        target_obj = None
                        for key, value in json_obj.items():
                            if key.startswith('tusjoh'):
                                target_obj = value
                                break
                        if target_obj and 'photo' in target_obj:
                            photo = target_obj['photo']
                        else:
                            photo = json_obj.get('photo')
                        if not photo:
                            props = json_obj.get('props', {})
                            pageProps = props.get('pageProps', {})
                            photo = pageProps.get('photo')

                        if photo:
                            result = {}
                            if 'mainMvUrls' in photo and photo['mainMvUrls']:
                                video_url = photo['mainMvUrls'][0].get('url', '')
                                if video_url:
                                    result = {
                                        'title': photo.get('caption', '无标题'),
                                        'nickName': photo.get('userName', '未知作者'),
                                        'type': 1,
                                        'videoUrl': video_url,
                                        'platform': 'kuaishou'
                                    }
                            elif 'ext_params' in photo and 'atlas' in photo['ext_params']:
                                atlas = photo['ext_params']['atlas']
                                http = atlas.get('cdn', [None])[0] or ''
                                image_list = []
                                if 'list' in atlas and isinstance(atlas['list'], list):
                                    for item in atlas['list']:
                                        image_list.append(f"https://{http}{item}")
                                if image_list:
                                    result = {
                                        'title': photo.get('caption', '无标题'),
                                        'nickName': photo.get('userName', '未知作者'),
                                        'type': 2,
                                        'imageList': image_list,
                                        'platform': 'kuaishou'
                                    }
                            if result:
                                await log_info('[快手] 解析成功（INIT_STATE）')
                                return result
                except json.JSONDecodeError:
                    json_obj = None
                except Exception as e:
                    await log_error('[快手] JSON解析失败', e)

            mv_match = re.search(r'"mainMvUrls"\s*:\s*\[\s*{\s*"url"\s*:\s*"([^"]+)"', html)
            if mv_match:
                video_url = mv_match.group(1).replace('\\u002F', '/').replace('\\/', '/')
                title_match = re.search(r'"caption"\s*:\s*"([^"]+)"', html)
                title = title_match.group(1) if title_match else '无标题'
                author_match = re.search(r'"userName"\s*:\s*"([^"]+)"', html)
                author = author_match.group(1) if author_match else '未知作者'
                result = {
                    'title': title,
                    'nickName': author,
                    'type': 1,
                    'videoUrl': video_url,
                    'platform': 'kuaishou'
                }
                await log_info('[快手] 解析成功（正则匹配视频）')
                return result

            atlas_match = re.search(r'"atlas"\s*:\s*{[^}]*"list"\s*:\s*\[([^\]]+)\]', html, re.DOTALL)
            if atlas_match:
                image_urls = re.findall(r'"([^"]+)"', atlas_match.group(1))
                if image_urls:
                    http_match = re.search(r'"cdn"\s*:\s*\[\s*"([^"]+)"', html)
                    http = http_match.group(1) if http_match else ''
                    image_list = [f"https://{http}{img}" for img in image_urls]
                    title_match = re.search(r'"caption"\s*:\s*"([^"]+)"', html)
                    title = title_match.group(1) if title_match else '无标题'
                    author_match = re.search(r'"userName"\s*:\s*"([^"]+)"', html)
                    author = author_match.group(1) if author_match else '未知作者'
                    result = {
                        'title': title,
                        'nickName': author,
                        'type': 2,
                        'imageList': image_list,
                        'platform': 'kuaishou'
                    }
                    await log_info('[快手] 解析成功（正则匹配图集）')
                    return result

            raise Exception('所有解析方法均失败')
    except Exception as e:
        await log_error('[快手] 解析失败', str(e))
        return None

# ---------- B站解析 ----------
async def parse_bilibili(url):
    try:
        await log_info(f'[B站] 开始解析: {url}')
        bv_match = re.search(r'(BV[a-zA-Z0-9]{10})', url)
        bvid = bv_match.group(1) if bv_match else None
        if not bvid:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, allow_redirects=True) as resp:
                    final_url = str(resp.url)
                    bv_match = re.search(r'(BV[a-zA-Z0-9]{10})', final_url)
                    bvid = bv_match.group(1) if bv_match else None
        if not bvid:
            raise Exception('未找到BV号')
        await log_info(f'[B站] 提取到BV号: {bvid}')

        async with aiohttp.ClientSession() as session:
            headers = {
                'User-Agent': random_ua(),
                'Referer': 'https://www.bilibili.com/'
            }
            api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
            info_data = await fetch_json(session, api_url, headers)
            if not info_data or info_data.get('code') != 0:
                raise Exception('视频信息获取失败')
            video_info = info_data['data']

            avid = video_info['aid']
            cid = video_info['cid']
            play_url = f"https://api.bilibili.com/x/player/playurl?avid={avid}&cid={cid}&qn=80&fnval=0&fourk=1"
            play_data = await fetch_json(session, play_url, headers)
            if not play_data or play_data.get('code') != 0:
                raise Exception('播放地址获取失败')
            durl = play_data.get('data', {}).get('durl', [])
            video_url = durl[0]['url'] if durl else None
            if not video_url:
                raise Exception('未找到可用的视频地址')

            result = {
                'title': video_info.get('title', '无标题'),
                'nickName': video_info.get('owner', {}).get('name', '未知作者'),
                'type': 1,
                'videoUrl': video_url,
                'cover': video_info.get('pic', ''),
                'bvid': bvid,
                'aid': avid,
                'cid': cid,
                'platform': 'bilibili'
            }
            await log_info('[B站] 解析成功')
            return result
    except Exception as e:
        await log_error('[B站] 解析失败', str(e))
        return None

# ---------- 小红书解析 ----------
async def parse_xiaohongshu(url):
    try:
        await log_info(f'[小红书] 开始解析: {url}')
        headers = {
            'User-Agent': random_ua(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'max-age=0',
            'Upgrade-Insecure-Requests': '1'
        }
        async with aiohttp.ClientSession() as session:
            html = await fetch_text(session, url, headers)
            if not html:
                raise Exception('页面获取失败')

            if '验证码' in html or 'captcha' in html:
                raise Exception('遇到验证码页面，请稍后重试')

            json_str = await extract_json_data(html, 'window.__INITIAL_STATE__')
            if json_str == '{}':
                json_str = await extract_json_data(html, 'window["__INITIAL_STATE__"]')
            json_str = json_str.replace('undefined', 'null')
            if json_str != '{}':
                try:
                    json_obj = json.loads(json_str)
                    if json_obj:
                        note_data = None
                        if 'note' in json_obj and 'noteDetailMap' in json_obj['note']:
                            note_detail_map = json_obj['note']['noteDetailMap']
                            first_id = next(iter(note_detail_map)) if note_detail_map else None
                            if first_id and 'note' in note_detail_map[first_id]:
                                note_data = note_detail_map[first_id]['note']
                        elif 'noteData' in json_obj and 'data' in json_obj['noteData']:
                            note_data = json_obj['noteData']['data'].get('noteData')
                        elif 'props' in json_obj and 'pageProps' in json_obj['props']:
                            note_data = json_obj['props']['pageProps'].get('noteData')
                        elif 'note' in json_obj:
                            note_data = json_obj['note']

                        if note_data:
                            result = {}
                            content_type = note_data.get('type', 'normal')
                            if content_type == 'video':
                                video_url = ''
                                if 'video' in note_data and 'media' in note_data['video']:
                                    media = note_data['video']['media']
                                    if 'stream' in media:
                                        if 'h265' in media['stream'] and media['stream']['h265']:
                                            video_url = media['stream']['h265'][0].get('masterUrl', '')
                                        elif 'h264' in media['stream'] and media['stream']['h264']:
                                            video_url = media['stream']['h264'][0].get('masterUrl', '')
                                    elif 'consumer' in note_data['video'] and 'originVideoKey' in note_data['video']['consumer']:
                                        video_url = 'https://sns-video-bd.xhscdn.com/' + note_data['video']['consumer']['originVideoKey']
                                if video_url:
                                    result = {
                                        'title': note_data.get('desc') or note_data.get('title') or '无标题',
                                        'nickName': note_data.get('user', {}).get('nickName') or note_data.get('user', {}).get('nickname') or note_data.get('user', {}).get('name') or '未知作者',
                                        'type': 1,
                                        'videoUrl': video_url,
                                        'platform': 'xiaohongshu'
                                    }
                            elif content_type == 'normal' or 'imageList' in note_data:
                                image_list = []
                                images = note_data.get('imageList', [])
                                for img in images:
                                    url = ''
                                    if 'urlDefault' in img:
                                        url = img['urlDefault']
                                    elif 'url' in img:
                                        url = img['url']
                                    elif 'infoList' in img and img['infoList'] and 'url' in img['infoList'][0]:
                                        url = img['infoList'][0]['url']
                                    elif 'stream' in img:
                                        if 'h264' in img['stream'] and img['stream']['h264']:
                                            url = img['stream']['h264'][0].get('masterUrl', '')
                                        elif 'h265' in img['stream'] and img['stream']['h265']:
                                            url = img['stream']['h265'][0].get('masterUrl', '')
                                    if url:
                                        image_list.append(url)
                                if image_list:
                                    result = {
                                        'title': note_data.get('desc') or note_data.get('title') or '无标题',
                                        'nickName': note_data.get('user', {}).get('nickName') or note_data.get('user', {}).get('nickname') or note_data.get('user', {}).get('name') or '未知作者',
                                        'type': 2,
                                        'imageList': image_list,
                                        'platform': 'xiaohongshu'
                                    }
                            if result:
                                await log_info('[小红书] 解析成功（INITIAL_STATE）')
                                return result
                except json.JSONDecodeError:
                    json_obj = None
                except Exception as e:
                    await log_error('[小红书] JSON解析失败', e)

            video_match = re.search(r'"originVideoKey":"([^"]+)"', html)
            if video_match:
                video_key = video_match.group(1)
                video_url = f"https://sns-video-bd.xhscdn.com/{video_key}"
                title_match = re.search(r'"desc":"([^"]+)"', html)
                title = title_match.group(1) if title_match else '无标题'
                author_match = re.search(r'"nickName":"([^"]+)"', html)
                author = author_match.group(1) if author_match else '未知作者'
                result = {
                    'title': title,
                    'nickName': author,
                    'type': 1,
                    'videoUrl': video_url,
                    'platform': 'xiaohongshu'
                }
                await log_info('[小红书] 解析成功（正则匹配视频）')
                return result

            img_matches = re.findall(r'"urlDefault":"([^"]+)"', html)
            if img_matches:
                image_list = [u.replace('\\u002F', '/') for u in img_matches]
                title_match = re.search(r'"desc":"([^"]+)"', html)
                title = title_match.group(1) if title_match else '无标题'
                author_match = re.search(r'"nickName":"([^"]+)"', html)
                author = author_match.group(1) if author_match else '未知作者'
                result = {
                    'title': title,
                    'nickName': author,
                    'type': 2,
                    'imageList': image_list,
                    'platform': 'xiaohongshu'
                }
                await log_info('[小红书] 解析成功（正则匹配图片）')
                return result

            raise Exception('所有解析方法均失败')
    except Exception as e:
        await log_error('[小红书] 解析失败', str(e))
        return None

# 主解析函数
async def parse_video(input_text: str) -> dict:
    try:
        if not input_text:
            return {'success': False, 'code': 400, 'message': '请输入视频链接', 'data': None}
        url = extract_url(input_text)
        if not url:
            return {'success': False, 'code': 400, 'message': '未找到有效的视频链接', 'data': None}
        platform = get_platform(url)
        await log_info(f'识别到平台: {platform}, URL: {url}')
        if platform == 'unknown':
            return {'success': False, 'code': 400, 'message': '暂不支持该平台，目前支持：抖音、快手、B站、小红书', 'data': None}
        parse_func = {
            'douyin': parse_douyin,
            'kuaishou': parse_kuaishou,
            'bilibili': parse_bilibili,
            'xiaohongshu': parse_xiaohongshu
        }.get(platform)
        if not parse_func:
            return {'success': False, 'code': 400, 'message': '不支持的平台', 'data': None}
        result = await parse_func(url)
        if not result:
            return {'success': False, 'code': 404, 'message': '解析失败，请检查链接是否有效或稍后重试', 'data': None}
        return {'success': True, 'code': 200, 'message': '解析成功', 'data': result}
    except Exception as e:
        await log_error('解析异常', e)
        return {'success': False, 'code': 500, 'message': f'解析异常: {str(e)}', 'data': None}