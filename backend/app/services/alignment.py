"""
歌词时间轴对齐服务

策略:
1. 如果已安装 stable-ts → 使用 AI forced alignment（精确逐字对齐）
2. 否则 → 使用均匀分配算法（根据视频时长 + 字符数量均匀分配时间）
"""

import asyncio
from typing import Callable
from app.services.furigana import annotate_line

# 检测是否有 stable-ts
try:
    import stable_whisper
    _HAS_STABLE_TS = True
except ImportError:
    _HAS_STABLE_TS = False


async def align_lyrics(
    vocals_path: str,
    lyrics_lines: list[dict],
    job_id: str,
    push_progress: Callable,
    jobs: dict,
) -> list[dict]:
    """对齐歌词时间轴"""
    loop = asyncio.get_event_loop()

    if _HAS_STABLE_TS:
        result = await loop.run_in_executor(
            None, _align_with_whisper, vocals_path, lyrics_lines, job_id, jobs
        )
    else:
        result = await loop.run_in_executor(
            None, _align_by_duration, vocals_path, lyrics_lines, job_id, jobs
        )
    return result


# ============ 方案 A: AI 对齐 (stable-ts) ============

def _align_with_whisper(
    vocals_path: str,
    lyrics_lines: list[dict],
    job_id: str,
    jobs: dict,
) -> list[dict]:
    """使用 stable-ts forced alignment"""
    import stable_whisper

    jobs[job_id]["message"] = "正在加载对齐模型..."
    jobs[job_id]["progress"] = 10

    try:
        model = stable_whisper.load_model("large-v3")
    except Exception:
        try:
            model = stable_whisper.load_model("medium")
        except Exception:
            model = stable_whisper.load_model("small")

    full_text = "\n".join(line["text"] for line in lyrics_lines)

    jobs[job_id]["message"] = "正在对齐时间轴..."
    jobs[job_id]["progress"] = 30

    result = model.align(vocals_path, full_text, language="ja")

    jobs[job_id]["progress"] = 70
    jobs[job_id]["message"] = "正在处理对齐结果..."

    aligned_lines = []
    segment_idx = 0

    for line in lyrics_lines:
        text = line["text"]
        if segment_idx < len(result.segments):
            seg = result.segments[segment_idx]
            words = []
            if hasattr(seg, 'words') and seg.words:
                for w in seg.words:
                    words.append({
                        "text": w.word.strip(),
                        "start": round(w.start, 3),
                        "end": round(w.end, 3),
                    })
            aligned_lines.append({
                "text": text,
                "ruby": line.get("ruby", annotate_line(text)),
                "start_time": round(seg.start, 3),
                "end_time": round(seg.end, 3),
                "words": words,
            })
            segment_idx += 1
        else:
            aligned_lines.append({
                "text": text,
                "ruby": line.get("ruby", annotate_line(text)),
                "start_time": line.get("start_time"),
                "end_time": line.get("end_time"),
                "words": [],
            })

    jobs[job_id]["progress"] = 90
    return aligned_lines


# ============ 方案 B: 均匀分配 (无需 AI 模型) ============

def _align_by_duration(
    vocals_path: str,
    lyrics_lines: list[dict],
    job_id: str,
    jobs: dict,
) -> list[dict]:
    """
    根据音频时长和每行字符数，均匀分配时间轴。
    同时为每行内的每个字均匀分配逐字时间。
    """
    jobs[job_id]["message"] = "正在计算时间轴（均匀分配模式）..."
    jobs[job_id]["progress"] = 20

    # 获取音频时长
    duration = _get_audio_duration(vocals_path)
    if duration <= 0:
        # 尝试从 job 中获取视频时长
        video_info = jobs[job_id].get("video_info", {})
        duration = video_info.get("duration", 180.0)  # 默认 3 分钟

    jobs[job_id]["progress"] = 40

    # 如果已有部分行有时间信息（如 LRC），只填充缺失的
    has_any_time = any(line.get("start_time") is not None for line in lyrics_lines)

    if has_any_time:
        aligned = _fill_missing_times(lyrics_lines, duration)
    else:
        aligned = _distribute_evenly(lyrics_lines, duration)

    jobs[job_id]["progress"] = 80
    jobs[job_id]["message"] = "时间轴分配完成"

    # 为每行生成逐字时间
    for line in aligned:
        if not line.get("words") and line.get("start_time") is not None:
            line["words"] = _distribute_chars(
                line["text"], line["start_time"], line["end_time"]
            )

    jobs[job_id]["progress"] = 90
    return aligned


def _get_audio_duration(audio_path: str) -> float:
    """用 ffprobe 获取音频时长"""
    import subprocess
    import json
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        info = json.loads(result.stdout)
        return float(info.get("format", {}).get("duration", 0))
    except Exception:
        return 0.0


def _distribute_evenly(lines: list[dict], duration: float) -> list[dict]:
    """将所有行均匀分配到音频时长内"""
    if not lines:
        return []

    # 预留前后各 5% 的空白（MV 通常有前奏和尾奏）
    margin = duration * 0.05
    usable_start = margin
    usable_end = duration - margin
    usable_duration = usable_end - usable_start

    # 按字符数加权分配
    total_chars = sum(len(line["text"]) for line in lines)
    if total_chars == 0:
        total_chars = len(lines)

    # 行间留 0.3 秒间隔
    gap = 0.3
    total_gaps = gap * (len(lines) - 1) if len(lines) > 1 else 0
    available = max(usable_duration - total_gaps, len(lines) * 1.0)

    current_time = usable_start
    aligned = []

    for line in lines:
        char_weight = len(line["text"]) / total_chars if total_chars > 0 else 1.0 / len(lines)
        line_duration = max(1.0, available * char_weight)  # 每行至少 1 秒

        start_time = round(current_time, 3)
        end_time = round(current_time + line_duration, 3)

        aligned.append({
            "text": line["text"],
            "ruby": line.get("ruby", annotate_line(line["text"])),
            "start_time": start_time,
            "end_time": end_time,
            "words": [],
        })

        current_time = end_time + gap

    return aligned


def _fill_missing_times(lines: list[dict], duration: float) -> list[dict]:
    """对已有部分时间信息的行，填充缺失的时间"""
    aligned = []

    for i, line in enumerate(lines):
        start = line.get("start_time")
        end = line.get("end_time")

        # 如果没有 end_time，用下一行的 start_time 或 +3 秒
        if start is not None and end is None:
            if i + 1 < len(lines) and lines[i + 1].get("start_time") is not None:
                end = lines[i + 1]["start_time"]
            else:
                end = start + 3.0

        # 如果完全没有时间信息，估算
        if start is None:
            if i > 0 and aligned[i - 1].get("end_time") is not None:
                start = aligned[i - 1]["end_time"] + 0.3
            else:
                start = 0.0
            end = start + 3.0

        aligned.append({
            "text": line["text"],
            "ruby": line.get("ruby", annotate_line(line["text"])),
            "start_time": round(start, 3),
            "end_time": round(end, 3),
            "words": [],
        })

    return aligned


def _distribute_chars(text: str, start: float, end: float) -> list[dict]:
    """将一行内的每个字符均匀分配时间"""
    if not text:
        return []

    duration = end - start
    char_duration = duration / len(text)
    words = []

    for i, char in enumerate(text):
        words.append({
            "text": char,
            "start": round(start + i * char_duration, 3),
            "end": round(start + (i + 1) * char_duration, 3),
        })

    return words
