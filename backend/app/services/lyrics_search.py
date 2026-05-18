"""
歌词搜索服务
从公开歌词源搜索带时间轴的 LRC 歌词

支持的源:
1. 网易云音乐 API（日语歌覆盖率高，返回 LRC 格式）
2. 歌词迷（国内歌词站，部分日语歌有 LRC）
"""

import re
import logging
import asyncio
from typing import Optional
from urllib.parse import quote

logger = logging.getLogger("ai-ktv")

# 网易云音乐 API 基地址（公开非官方 API）
NETEASE_API = "https://music.163.com/api"


async def search_lyrics(
    keyword: str,
    artist: str = "",
    limit: int = 5,
) -> list[dict]:
    """
    搜索歌词，返回候选列表。

    Args:
        keyword: 歌曲名/关键词
        artist: 歌手名（可选，用于精确匹配）
        limit: 返回候选数量

    Returns:
        [
            {
                "id": "netease_12345",
                "source": "netease",
                "title": "歌名",
                "artist": "歌手",
                "album": "专辑",
                "duration": 228,          # 秒
                "has_lrc": True,
                "preview": "[00:15.00]第一句歌词...",
            },
            ...
        ]
    """
    results = []

    # 搜索网易云
    try:
        netease_results = await _netease_search(keyword, artist, limit)
        results.extend(netease_results)
    except Exception as e:
        logger.warning(f"网易云搜索失败: {e}")

    return results[:limit]


async def fetch_lyrics(source: str, song_id: str) -> dict:
    """
    获取指定歌曲的完整 LRC 歌词。

    Args:
        source: 来源（"netease"）
        song_id: 歌曲 ID

    Returns:
        {
            "lrc": "[00:15.00]歌词内容...",     # 原文 LRC
            "tlrc": "[00:15.00]翻译...",         # 翻译 LRC（如有）
            "source": "netease",
            "song_id": "12345",
        }
    """
    if source == "netease":
        return await _netease_fetch_lyrics(song_id)
    else:
        raise ValueError(f"不支持的歌词源: {source}")


# ============ 网易云音乐 ============

async def _netease_search(
    keyword: str, artist: str, limit: int
) -> list[dict]:
    """通过网易云音乐 API 搜索歌曲"""
    import aiohttp

    search_term = f"{keyword} {artist}".strip()
    url = f"{NETEASE_API}/search/get"
    params = {
        "s": search_term,
        "type": 1,       # 1=单曲
        "limit": limit,
        "offset": 0,
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://music.163.com/",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                raise RuntimeError(f"网易云搜索失败: HTTP {resp.status}")
            data = await resp.json(content_type=None)

    songs = data.get("result", {}).get("songs", [])
    results = []

    for song in songs:
        song_id = str(song.get("id", ""))
        title = song.get("name", "")
        artists = ", ".join(a.get("name", "") for a in song.get("artists", []))
        album = song.get("album", {}).get("name", "")
        duration = song.get("duration", 0) // 1000  # ms → s

        results.append({
            "id": song_id,
            "source": "netease",
            "title": title,
            "artist": artists,
            "album": album,
            "duration": duration,
            "has_lrc": True,  # 网易云基本都有 LRC
            "preview": "",
        })

    return results


async def _netease_fetch_lyrics(song_id: str) -> dict:
    """获取网易云音乐的 LRC 歌词"""
    import aiohttp

    url = f"{NETEASE_API}/song/lyric"
    params = {
        "id": song_id,
        "lv": 1,   # 原文歌词
        "tv": 1,   # 翻译歌词
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://music.163.com/",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                raise RuntimeError(f"获取歌词失败: HTTP {resp.status}")
            data = await resp.json(content_type=None)

    lrc_text = data.get("lrc", {}).get("lyric", "")
    tlrc_text = data.get("tlyric", {}).get("lyric", "")

    if not lrc_text:
        raise RuntimeError("该歌曲暂无歌词")

    # 清理 LRC：去除头部元信息行如 [ti:xxx] [ar:xxx] [by:xxx]
    lrc_text = _clean_lrc_metadata(lrc_text)

    # 生成预览（前3行有效歌词）
    preview_lines = []
    for line in lrc_text.split("\n"):
        if re.match(r'\[\d{2}:\d{2}', line) and len(preview_lines) < 3:
            preview_lines.append(line.strip())

    return {
        "lrc": lrc_text,
        "tlrc": tlrc_text if tlrc_text else None,
        "source": "netease",
        "song_id": song_id,
        "preview": "\n".join(preview_lines),
    }


def _clean_lrc_metadata(lrc: str) -> str:
    """去除 LRC 中的元信息标签，只保留歌词行"""
    # 常见的元信息关键词（中日英）
    meta_keywords = [
        '作词', '作曲', '编曲', '制作人', '混音', '录音', '母带',
        '作詞', '作曲', '編曲',
        'lyrics', 'composer', 'arranger', 'producer', 'mix', 'master',
    ]
    meta_pattern = re.compile(
        r'^\[\d{2}:\d{2}[\.:]\d{2,3}\]\s*(' + '|'.join(re.escape(k) for k in meta_keywords) + r')\s*[:：]',
        re.IGNORECASE
    )

    cleaned_lines = []
    for line in lrc.split("\n"):
        line = line.strip()
        # 跳过标准元信息标签: [ti:xxx], [ar:xxx], [al:xxx], [by:xxx], [offset:xxx]
        if re.match(r'^\[(ti|ar|al|by|offset|re|ve|tool)\s*:', line, re.IGNORECASE):
            continue
        # 跳过带时间标签的元信息行（如 [00:00.000] 作词 : xxx）
        if meta_pattern.match(line):
            continue
        if line:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)
