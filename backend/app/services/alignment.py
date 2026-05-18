"""
歌词时间轴对齐服务

策略:
1. 如果已安装 stable-ts → 先用 Whisper 转录获得时间戳，再匹配用户歌词
2. 否则 → 使用均匀分配算法（根据视频时长 + 字符数量均匀分配时间）
"""

import asyncio
import logging
from typing import Callable
from app.services.furigana import annotate_line

logger = logging.getLogger("ai-ktv")

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
    """
    使用 stable-ts 对齐歌词。
    
    策略：先用 Whisper transcribe 获取完整转录+时间戳，
    然后将用户歌词的每一行与转录结果做文本匹配，映射时间戳。
    如果转录质量太差，回退到基于音频能量的智能分配。
    """
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

    jobs[job_id]["message"] = "正在转录音频获取时间戳..."
    jobs[job_id]["progress"] = 20

    # Step 1: 先完整转录人声，获取逐字时间戳
    result = model.transcribe(vocals_path, language="ja")

    jobs[job_id]["progress"] = 60
    jobs[job_id]["message"] = "正在匹配歌词行..."

    # Step 2: 从转录结果中提取所有 word 级别的时间戳
    all_words = []
    for seg in result.segments:
        if hasattr(seg, 'words') and seg.words:
            for w in seg.words:
                all_words.append({
                    "text": w.word.strip(),
                    "start": w.start,
                    "end": w.end,
                })

    logger.info(f"[{job_id}] 转录得到 {len(all_words)} 个词")

    # 检查转录质量：如果词数太少或者文本高度重复，认为转录失败
    trans_text = "".join(w["text"] for w in all_words)
    user_text = "".join(line["text"] for line in lyrics_lines)
    
    # 判断转录是否有效：至少应该有用户歌词 30% 的字符量
    is_valid = len(trans_text) > len(user_text) * 0.3
    
    # 检查是否高度重复（如全是同一句）
    if is_valid and len(set(trans_text)) < 10:
        is_valid = False
        
    if not is_valid or not all_words:
        logger.warning(f"[{job_id}] 转录质量差(len={len(trans_text)}, user={len(user_text)})，使用能量检测分配")
        jobs[job_id]["message"] = "转录质量不足，使用智能分配..."
        return _align_by_energy(vocals_path, lyrics_lines, job_id, jobs)

    # Step 3: 将用户歌词的每一行匹配到转录结果的时间段
    aligned_lines = _match_lyrics_to_transcription(lyrics_lines, all_words)

    jobs[job_id]["progress"] = 90
    jobs[job_id]["message"] = "对齐完成"

    return aligned_lines


def _align_by_energy(
    vocals_path: str,
    lyrics_lines: list[dict],
    job_id: str,
    jobs: dict,
) -> list[dict]:
    """
    基于音频能量检测的智能时间分配。
    检测人声段落（有声区间），然后将歌词行分配到有声区间内。
    """
    import subprocess
    import json
    import struct
    import wave
    
    jobs[job_id]["progress"] = 65
    
    # 获取音频时长
    duration = _get_audio_duration(vocals_path)
    if duration <= 0:
        video_info = jobs[job_id].get("video_info", {})
        duration = video_info.get("duration", 180.0)
    
    # 使用 ffmpeg 的 silencedetect 检测有声区间
    vocal_segments = _detect_vocal_segments(vocals_path, duration)
    
    # 如果检测不到有声段落（分离效果差），降低阈值重试
    if not vocal_segments:
        vocal_segments = _detect_vocal_segments(vocals_path, duration, noise_db=-40, min_silence=3.0)
    
    # 仍然没有，直接用均匀分配但基于视频时长
    if not vocal_segments:
        logger.warning(f"[{job_id}] 能量检测失败，使用均匀分配")
        return _align_by_duration(vocals_path, lyrics_lines, job_id, jobs)
    
    # 将歌词行分配到有声段落中
    aligned = _distribute_to_segments(lyrics_lines, vocal_segments)
    
    # 为每行生成逐字时间
    for line in aligned:
        if not line.get("words") and line.get("start_time") is not None:
            line["words"] = _distribute_chars(
                line["text"], line["start_time"], line["end_time"]
            )
    
    jobs[job_id]["progress"] = 90
    return aligned


def _detect_vocal_segments(vocals_path: str, duration: float) -> list[tuple]:
    """
    使用 FFmpeg silencedetect 检测有声区间。
    返回 [(start, end), ...] 列表。
    """
    import subprocess
    
    # silencedetect 参数：噪声阈值 -30dB，静音最短 1.5 秒
    cmd = [
        "ffmpeg", "-i", vocals_path,
        "-af", "silencedetect=noise=-30dB:d=1.5",
        "-f", "null", "-"
    ]
    
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        )
        stderr = result.stderr
    except Exception:
        return []
    
    # 解析 silencedetect 输出
    import re
    silence_starts = []
    silence_ends = []
    
    for line in stderr.split('\n'):
        m = re.search(r'silence_start: ([\d.]+)', line)
        if m:
            silence_starts.append(float(m.group(1)))
        m = re.search(r'silence_end: ([\d.]+)', line)
        if m:
            silence_ends.append(float(m.group(1)))
    
    # 从静音区间推导出有声区间
    vocal_segments = []
    
    if not silence_starts and not silence_ends:
        # 没有检测到静音，整段都是人声
        return [(0, duration)]
    
    # 如果第一个静音不是从头开始，说明开头有人声
    if silence_starts and silence_starts[0] > 1.0:
        vocal_segments.append((0, silence_starts[0]))
    
    # 两段静音之间就是有声
    for i in range(len(silence_ends)):
        seg_start = silence_ends[i]
        seg_end = silence_starts[i + 1] if i + 1 < len(silence_starts) else duration
        if seg_end - seg_start > 0.5:  # 至少 0.5 秒才算有效段落
            vocal_segments.append((seg_start, seg_end))
    
    return vocal_segments


def _distribute_to_segments(
    lyrics_lines: list[dict],
    vocal_segments: list[tuple],
) -> list[dict]:
    """将歌词行均匀分配到有声段落中"""
    if not lyrics_lines or not vocal_segments:
        return []
    
    # 计算有声段落总时长
    total_vocal_duration = sum(end - start for start, end in vocal_segments)
    
    # 按字符数加权分配
    total_chars = sum(len(line["text"]) for line in lyrics_lines)
    if total_chars == 0:
        total_chars = len(lyrics_lines)
    
    # 为每行计算目标时长
    line_durations = []
    for line in lyrics_lines:
        weight = len(line["text"]) / total_chars
        dur = max(1.5, total_vocal_duration * weight)
        line_durations.append(dur)
    
    # 归一化使总时长不超过有声段落总时长
    total_assigned = sum(line_durations)
    if total_assigned > total_vocal_duration:
        scale = total_vocal_duration / total_assigned * 0.95
        line_durations = [d * scale for d in line_durations]
    
    # 将歌词行按顺序填入有声段落
    aligned = []
    seg_idx = 0
    time_in_seg = vocal_segments[0][0] if vocal_segments else 0
    
    for i, line in enumerate(lyrics_lines):
        # 如果当前段落剩余时间不够，跳到下一段
        while seg_idx < len(vocal_segments):
            seg_start, seg_end = vocal_segments[seg_idx]
            remaining = seg_end - time_in_seg
            if remaining >= 0.5:
                break
            seg_idx += 1
            if seg_idx < len(vocal_segments):
                time_in_seg = vocal_segments[seg_idx][0]
        
        if seg_idx >= len(vocal_segments):
            # 有声段落用完了，把剩余歌词紧接着排
            start_time = time_in_seg
            end_time = start_time + line_durations[i]
        else:
            start_time = time_in_seg
            end_time = min(start_time + line_durations[i], vocal_segments[seg_idx][1])
        
        aligned.append({
            "text": line["text"],
            "ruby": line.get("ruby", annotate_line(line["text"])),
            "start_time": round(start_time, 3),
            "end_time": round(end_time, 3),
            "words": [],
        })
        
        time_in_seg = end_time + 0.2  # 行间间隔 0.2 秒
    
    return aligned


def _match_lyrics_to_transcription(
    lyrics_lines: list[dict],
    all_words: list[dict],
) -> list[dict]:
    """
    将用户歌词行与 Whisper 转录结果进行匹配，获取时间戳。

    核心策略：
    1. 把转录 words 拼成一个长字符串，同时构建字符→时间的映射表
    2. 把用户所有歌词也拼成一个长字符串
    3. 用 difflib.SequenceMatcher 做全局模糊对齐，找到用户歌词中每个字符
       在转录文本中的对应位置
    4. 根据用户的行边界，从映射表中取出每行的 start/end 时间
    """
    import re
    from difflib import SequenceMatcher

    # ---- Step 1: 构建转录的字符级时间映射 ----
    char_times = []  # [{char, start, end}, ...]
    for w in all_words:
        word_text = w["text"]
        if not word_text:
            continue
        char_dur = (w["end"] - w["start"]) / max(1, len(word_text))
        for i, ch in enumerate(word_text):
            char_times.append({
                "char": ch,
                "start": w["start"] + i * char_dur,
                "end": w["start"] + (i + 1) * char_dur,
            })

    trans_text = "".join(ct["char"] for ct in char_times)

    # ---- Step 2: 构建用户歌词的行→字符偏移映射 ----
    user_text = ""
    line_spans = []  # [(start_offset, end_offset, line_idx), ...]
    for idx, line in enumerate(lyrics_lines):
        text = line["text"].strip()
        if not text:
            continue
        start_off = len(user_text)
        user_text += text
        end_off = len(user_text)
        line_spans.append((start_off, end_off, idx))

    logger.info(
        f"匹配: 用户歌词 {len(user_text)} 字 / {len(line_spans)} 行, "
        f"转录 {len(trans_text)} 字"
    )

    if not user_text or not trans_text:
        # 无法匹配，返回空时间
        return [
            {
                "text": line["text"],
                "ruby": line.get("ruby", annotate_line(line["text"])),
                "start_time": 0.0,
                "end_time": 3.0,
                "words": [],
            }
            for line in lyrics_lines
        ]

    # ---- Step 3: 清理文本后做全局序列对齐 ----
    def _clean(t: str) -> str:
        return re.sub(r'[\s\u3000、。！？…・「」『』（）\(\)\[\]【】,\.!?\u300c\u300d]', '', t)

    clean_user = _clean(user_text)
    clean_trans = _clean(trans_text)

    # 构建 clean_user[i] → user_text 原始偏移 的映射
    cu_to_user = []
    for i, ch in enumerate(user_text):
        if _clean(ch):
            cu_to_user.append(i)

    # 构建 clean_trans[i] → char_times 索引 的映射
    ct_to_idx = []
    for i, ch in enumerate(trans_text):
        if _clean(ch):
            ct_to_idx.append(i)

    # 用 SequenceMatcher 找匹配块
    sm = SequenceMatcher(None, clean_user, clean_trans, autojunk=False)
    matching_blocks = sm.get_matching_blocks()

    # 构建 user_text 中每个字符位置到 char_times 索引的映射
    # -1 表示该字符没有匹配到转录
    user_to_trans = [-1] * len(user_text)

    for block in matching_blocks:
        a_start, b_start, size = block
        if size == 0:
            continue
        for k in range(size):
            cu_pos = a_start + k  # clean_user 中的位置
            ct_pos = b_start + k  # clean_trans 中的位置
            if cu_pos < len(cu_to_user) and ct_pos < len(ct_to_idx):
                user_offset = cu_to_user[cu_pos]
                trans_idx = ct_to_idx[ct_pos]
                user_to_trans[user_offset] = trans_idx

    # ---- Step 4: 根据行边界提取时间 ----
    aligned_lines = []

    for span_start, span_end, line_idx in line_spans:
        line = lyrics_lines[line_idx]
        line_text = line["text"].strip()

        # 收集这行中所有匹配到的 char_times 索引
        matched_indices = []
        for pos in range(span_start, span_end):
            ti = user_to_trans[pos]
            if ti >= 0:
                matched_indices.append(ti)

        if matched_indices:
            first_idx = min(matched_indices)
            last_idx = max(matched_indices)
            start_time = char_times[first_idx]["start"]
            end_time = char_times[last_idx]["end"]

            # 逐字时间：按用户歌词的每个字符分配
            # 对匹配到的字符用转录时间，未匹配的做插值
            words = _interpolate_word_times(
                line_text, span_start, user_to_trans, char_times,
                start_time, end_time
            )
        else:
            # 这一行完全没有匹配到转录
            # 尝试从前后行推断时间
            start_time = None
            end_time = None
            words = []

        aligned_lines.append({
            "text": line_text,
            "ruby": line.get("ruby", annotate_line(line_text)),
            "start_time": round(start_time, 3) if start_time is not None else None,
            "end_time": round(end_time, 3) if end_time is not None else None,
            "words": words,
        })

    # ---- Step 5: 填补未匹配行的时间（前后插值） ----
    _fill_gaps(aligned_lines)

    return aligned_lines


def _interpolate_word_times(
    line_text: str,
    span_start: int,
    user_to_trans: list,
    char_times: list,
    line_start: float,
    line_end: float,
) -> list[dict]:
    """
    为一行歌词的每个字符生成逐字时间。
    匹配到转录的字符使用转录时间，未匹配的字符在前后已知时间点之间线性插值。
    """
    n = len(line_text)
    # 先收集每个字符的已知时间
    known = [None] * n  # (start, end) or None
    for i in range(n):
        ti = user_to_trans[span_start + i]
        if ti >= 0 and ti < len(char_times):
            known[i] = (char_times[ti]["start"], char_times[ti]["end"])

    # 线性插值填充未知位置
    times = [None] * n
    for i in range(n):
        if known[i] is not None:
            times[i] = known[i]

    # 前向/后向填充
    if times[0] is None:
        times[0] = (line_start, line_start)
    if times[-1] is None:
        times[-1] = (line_end, line_end)

    # 找到所有已知点，对间隙做线性插值
    known_positions = [i for i in range(n) if times[i] is not None]

    for ki in range(len(known_positions) - 1):
        p1 = known_positions[ki]
        p2 = known_positions[ki + 1]
        if p2 - p1 <= 1:
            continue
        # 线性插值 p1+1 到 p2-1
        t1_start = times[p1][0]
        t2_start = times[p2][0]
        for j in range(p1 + 1, p2):
            ratio = (j - p1) / (p2 - p1)
            t = t1_start + ratio * (t2_start - t1_start)
            times[j] = (t, t)

    # 构建 words 列表，确保时间连续
    words = []
    for i in range(n):
        if times[i] is not None:
            s = times[i][0]
        else:
            s = line_start + (line_end - line_start) * i / n

        if i + 1 < n and times[i + 1] is not None:
            e = times[i + 1][0]
        elif times[i] is not None:
            e = times[i][1]
        else:
            e = line_start + (line_end - line_start) * (i + 1) / n

        # 确保 end >= start
        e = max(e, s + 0.01)

        words.append({
            "text": line_text[i],
            "start": round(s, 3),
            "end": round(e, 3),
        })

    return words


def _fill_gaps(aligned_lines: list[dict]):
    """
    填补未匹配行的时间。
    找到前后有时间的行，在间隙中均匀分配。
    """
    n = len(aligned_lines)
    if not n:
        return

    # 找到所有有时间的行的索引
    timed = [(i, aligned_lines[i]) for i in range(n)
             if aligned_lines[i]["start_time"] is not None]

    if not timed:
        # 所有行都没有时间，无法填补
        return

    # 处理开头无时间的行
    first_timed_idx = timed[0][0]
    if first_timed_idx > 0:
        first_start = timed[0][1]["start_time"]
        # 把开头无时间的行排在第一个有时间行之前
        gap_lines = first_timed_idx
        per_line = min(3.0, first_start / max(1, gap_lines + 1))
        for i in range(first_timed_idx):
            s = max(0, first_start - (first_timed_idx - i) * per_line)
            e = s + per_line * 0.9
            aligned_lines[i]["start_time"] = round(s, 3)
            aligned_lines[i]["end_time"] = round(e, 3)
            if not aligned_lines[i]["words"]:
                aligned_lines[i]["words"] = _distribute_chars(
                    aligned_lines[i]["text"], s, e
                )

    # 处理中间无时间的段
    for ti in range(len(timed) - 1):
        idx1 = timed[ti][0]
        idx2 = timed[ti + 1][0]
        if idx2 - idx1 <= 1:
            continue
        # idx1+1 到 idx2-1 是无时间的行
        gap_start = aligned_lines[idx1]["end_time"]
        gap_end = aligned_lines[idx2]["start_time"]
        gap_count = idx2 - idx1 - 1
        if gap_end <= gap_start:
            gap_end = gap_start + gap_count * 2.0
        per_line = (gap_end - gap_start) / (gap_count + 1)  # 留点间隔
        for k, i in enumerate(range(idx1 + 1, idx2)):
            s = gap_start + (k + 0.5) * per_line - per_line * 0.45
            e = s + per_line * 0.9
            aligned_lines[i]["start_time"] = round(s, 3)
            aligned_lines[i]["end_time"] = round(e, 3)
            if not aligned_lines[i]["words"]:
                aligned_lines[i]["words"] = _distribute_chars(
                    aligned_lines[i]["text"], s, e
                )

    # 处理末尾无时间的行
    last_timed_idx = timed[-1][0]
    if last_timed_idx < n - 1:
        last_end = timed[-1][1]["end_time"]
        remaining = n - 1 - last_timed_idx
        per_line = 3.0
        for k, i in enumerate(range(last_timed_idx + 1, n)):
            s = last_end + k * per_line + 0.2
            e = s + per_line * 0.9
            aligned_lines[i]["start_time"] = round(s, 3)
            aligned_lines[i]["end_time"] = round(e, 3)
            if not aligned_lines[i]["words"]:
                aligned_lines[i]["words"] = _distribute_chars(
                    aligned_lines[i]["text"], s, e
                )


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

    # 预留前后各 10% 的空白（MV 通常有前奏和尾奏）
    margin_start = duration * 0.10
    margin_end = duration * 0.05
    usable_start = margin_start
    usable_end = duration - margin_end
    usable_duration = usable_end - usable_start

    # 按字符数加权分配
    total_chars = sum(len(line["text"]) for line in lines)
    if total_chars == 0:
        total_chars = len(lines)

    # 行间留 0.5 秒间隔
    gap = 0.5
    total_gaps = gap * (len(lines) - 1) if len(lines) > 1 else 0
    available = max(usable_duration - total_gaps, len(lines) * 1.0)

    current_time = usable_start
    aligned = []

    for line in lines:
        char_weight = len(line["text"]) / total_chars if total_chars > 0 else 1.0 / len(lines)
        line_duration = max(1.5, available * char_weight)  # 每行至少 1.5 秒

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
