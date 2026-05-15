"""
视频合成服务
使用 FFmpeg 将视频画面 + 伴奏音轨 + ASS 字幕合成为最终 KTV 视频
"""

import asyncio
from typing import Callable


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
    # 获取视频时长用于计算进度
    duration = jobs[job_id].get("video_info", {}).get("duration", 0)

    # FFmpeg 命令:
    # - 输入原视频 (只取视频流)
    # - 输入伴奏音频 (替换原音轨)
    # - 烧入 ASS 字幕 (硬字幕)
    # - 输出 H.264 + AAC 的 mp4
    #
    # 注意: subtitle_path 中的反斜杠和冒号需要转义
    escaped_sub = subtitle_path.replace("\\", "/").replace(":", "\\:")

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,           # 原视频
        "-i", audio_path,           # 伴奏音频
        "-map", "0:v:0",            # 取第一个输入的视频流
        "-map", "1:a:0",            # 取第二个输入的音频流
        "-vf", f"ass='{escaped_sub}'",  # 烧入字幕
        "-c:v", "libx264",          # H.264 编码
        "-preset", "medium",        # 编码速度/质量平衡
        "-crf", "23",               # 质量参数
        "-c:a", "aac",              # AAC 音频编码
        "-b:a", "192k",             # 音频比特率
        "-movflags", "+faststart",  # 支持边下边播
        "-progress", "pipe:1",      # 输出进度到 stdout
        output_path,
    ]

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
