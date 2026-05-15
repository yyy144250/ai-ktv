"""
歌词识别服务
使用 Whisper + stable-ts 对日语歌曲人声进行识别，获取逐字时间戳
"""

import asyncio
from typing import Callable
from app.services.furigana import annotate_line


async def recognize_japanese_lyrics(
    vocals_path: str,
    job_id: str,
    push_progress: Callable,
    jobs: dict,
) -> list[dict]:
    """
    使用 Whisper 识别日语歌词

    Args:
        vocals_path: 人声音频文件路径
        job_id: 任务 ID
        push_progress: 进度推送函数
        jobs: 全局任务字典

    Returns:
        [{text, ruby, start_time, end_time, words}, ...]
    """
    # 在线程池中运行（Whisper 是同步的）
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _recognize_sync, vocals_path, job_id, jobs)
    return result


def _recognize_sync(vocals_path: str, job_id: str, jobs: dict) -> list[dict]:
    """同步版本的歌词识别"""
    import stable_whisper

    # 加载模型 (使用 large-v3 获得最佳日语识别效果)
    # 如果 GPU 不足，可降级为 medium 或 small
    jobs[job_id]["message"] = "正在加载 Whisper 模型 (首次可能较慢)..."
    jobs[job_id]["progress"] = 10

    try:
        model = stable_whisper.load_model("large-v3")
    except Exception:
        try:
            model = stable_whisper.load_model("medium")
        except Exception:
            model = stable_whisper.load_model("small")

    jobs[job_id]["message"] = "正在识别日语歌词..."
    jobs[job_id]["progress"] = 30

    # 转录
    result = model.transcribe(
        vocals_path,
        language="ja",
        word_timestamps=True,
    )

    jobs[job_id]["progress"] = 70
    jobs[job_id]["message"] = "正在处理识别结果..."

    # 解析结果
    lines = []
    for segment in result.segments:
        text = segment.text.strip()
        if not text:
            continue

        # 获取逐字时间戳
        words = []
        if hasattr(segment, 'words') and segment.words:
            for w in segment.words:
                words.append({
                    "text": w.word.strip(),
                    "start": round(w.start, 3),
                    "end": round(w.end, 3),
                })

        # 假名标注
        ruby = annotate_line(text)

        lines.append({
            "text": text,
            "ruby": ruby,
            "start_time": round(segment.start, 3),
            "end_time": round(segment.end, 3),
            "words": words,
        })

    jobs[job_id]["progress"] = 90
    return lines
