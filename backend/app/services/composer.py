"""
视频合成服务
使用 FFmpeg 将视频画面 + 伴奏音轨 + ASS 字幕合成为最终 KTV 视频

策略:
1. 如果 FFmpeg 支持 libass → 硬字幕烧入（ass 滤镜）
2. 否则 → 软字幕嵌入（MKV 容器封装，播放器自动渲染）
"""

import asyncio
import os
import subprocess
from typing import Callable

# 检测 FFmpeg 是否支持 ass 滤镜
_HAS_LIBASS = False
try:
    result = subprocess.run(
        ["ffmpeg", "-filters"],
        capture_output=True, text=True, timeout=5,
    )
    # 精确匹配 "ass" 滤镜（独立词，不是 allpass/bandpass 等）
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "ass":
            _HAS_LIBASS = True
            break
except Exception:
    pass


async def compose_video(
    video_path: str,
    audio_path: str,
    subtitle_path: str,
    output_path: str,
    job_id: str,
    push_progress: Callable,
    jobs: dict,
):
    """
    合成最终 KTV 视频

    Args:
        video_path: 原始视频路径
        audio_path: 伴奏音频路径
        subtitle_path: ASS 字幕路径
        output_path: 输出视频路径
        job_id: 任务 ID
        push_progress: 进度推送函数
        jobs: 全局任务字典
    """
    duration = jobs[job_id].get("video_info", {}).get("duration", 0)

    if _HAS_LIBASS:
        cmd = _build_hardburn_cmd(video_path, audio_path, subtitle_path, output_path)
        jobs[job_id]["message"] = "正在合成视频（硬字幕模式）..."
    else:
        # 软字幕需要用 MKV 容器（MP4 不支持 ASS 软字幕）
        if output_path.endswith(".mp4"):
            output_path = output_path.rsplit(".", 1)[0] + ".mkv"
            # 更新 job 中的路径
            jobs[job_id]["_output_path_override"] = output_path
        cmd = _build_softsub_cmd(video_path, audio_path, subtitle_path, output_path)
        jobs[job_id]["message"] = "正在合成视频（软字幕模式）..."

    await push_progress(job_id, jobs[job_id])

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # 解析 FFmpeg 进度输出
    assert proc.stdout
    async for line in proc.stdout:
        text = line.decode("utf-8", errors="replace").strip()
        if text.startswith("out_time_ms="):
            try:
                time_ms = int(text.split("=")[1])
                time_s = time_ms / 1_000_000
                if duration > 0:
                    pct = min(95, int(20 + (time_s / duration) * 75))
                    jobs[job_id]["progress"] = pct
                    jobs[job_id]["message"] = f"正在合成视频 {pct - 20:.0f}%..."
                    await push_progress(job_id, jobs[job_id])
            except (ValueError, ZeroDivisionError):
                pass

    await proc.wait()

    if proc.returncode != 0:
        stderr_output = ""
        if proc.stderr:
            stderr_bytes = await proc.stderr.read()
            stderr_output = stderr_bytes.decode("utf-8", errors="replace")[-500:]
        raise RuntimeError(f"FFmpeg 合成失败 (code={proc.returncode}): {stderr_output}")

    return output_path


def _build_hardburn_cmd(video_path, audio_path, subtitle_path, output_path):
    """硬字幕烧入命令（需要 libass）"""
    abs_sub = os.path.abspath(subtitle_path)
    escaped_sub = (
        abs_sub
        .replace("\\", "/")
        .replace(":", "\\:")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("'", "\\'")
    )
    return [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-vf", f"ass={escaped_sub}",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-progress", "pipe:1",
        output_path,
    ]


def _build_softsub_cmd(video_path, audio_path, subtitle_path, output_path):
    """软字幕嵌入命令（不需要 libass，用 MKV 容器）"""
    return [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-i", subtitle_path,
        "-map", "0:v:0",           # 视频流
        "-map", "1:a:0",           # 伴奏音频流
        "-map", "2:0",             # ASS 字幕流
        "-c:v", "copy",            # 视频直接复制（不重新编码，速度快）
        "-c:a", "aac",
        "-b:a", "192k",
        "-c:s", "ass",             # 字幕编码保持 ASS
        "-metadata:s:s:0", "language=jpn",
        "-metadata:s:s:0", "title=KTV Lyrics",
        "-progress", "pipe:1",
        output_path,
    ]
