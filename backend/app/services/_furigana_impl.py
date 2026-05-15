"""
振り仮名(假名标注)服务 - 实现
使用 fugashi + unidic-lite 对日语汉字自动标注假名读音
"""

import re
from typing import Optional

try:
    import fugashi
    import jaconv
    _tagger: Optional[fugashi.Tagger] = None
    _HAS_FUGASHI = True
except ImportError:
    _tagger = None
    _HAS_FUGASHI = False


def get_tagger():
    """延迟初始化 MeCab tagger"""
    global _tagger
    if not _HAS_FUGASHI:
        return None
    if _tagger is None:
        try:
            _tagger = fugashi.Tagger()
        except Exception:
            pass
    return _tagger


def is_kanji(char: str) -> bool:
    """判断字符是否是汉字"""
    code = ord(char)
    return (0x4E00 <= code <= 0x9FFF or
            0x3400 <= code <= 0x4DBF or
            0x20000 <= code <= 0x2A6DF or
            0xF900 <= code <= 0xFAFF)


def contains_kanji(text: str) -> bool:
    """判断文本是否包含汉字"""
    return any(is_kanji(c) for c in text)


def get_reading(word) -> Optional[str]:
    """从 fugashi Word 对象获取假名读音"""
    try:
        if hasattr(word, 'feature') and word.feature:
            parts = word.feature
            # 尝试获取 kana 属性
            if hasattr(parts, 'kana') and parts.kana:
                return jaconv.kata2hira(parts.kana)
            if hasattr(parts, 'reading') and parts.reading:
                return jaconv.kata2hira(parts.reading)
            # 尝试通过字符串分割获取
            raw = str(parts) if not isinstance(parts, str) else parts
            feature_parts = raw.split(",")
            for idx in [7, 8, 6, 9]:
                if idx < len(feature_parts):
                    reading = feature_parts[idx].strip()
                    if reading and reading != '*' and reading != '':
                        return jaconv.kata2hira(reading)
    except Exception:
        pass
    return None


def annotate_word(surface: str, reading: Optional[str]) -> list[dict]:
    """
    为单个词生成 ruby 标注
    返回: [{char: "漢", reading: "かん"}, {char: "字", reading: "じ"}]
    """
    if not reading or not contains_kanji(surface):
        return [{"char": c, "reading": ""} for c in surface]

    result = []

    if all(is_kanji(c) for c in surface):
        # 全是汉字，按字数均分假名
        if len(reading) >= len(surface):
            chars_per = len(reading) // len(surface)
            remainder = len(reading) % len(surface)
            idx = 0
            for i, c in enumerate(surface):
                take = chars_per + (1 if i < remainder else 0)
                result.append({"char": c, "reading": reading[idx:idx+take]})
                idx += take
        else:
            result.append({"char": surface, "reading": reading})
    else:
        result = _annotate_mixed(surface, reading)

    return result


def _annotate_mixed(surface: str, reading: str) -> list[dict]:
    """处理汉字+假名混合的词"""
    result = []

    # 分段：连续汉字一段，连续非汉字一段
    segments = []
    current = ""
    current_is_kanji = False

    for i, c in enumerate(surface):
        ck = is_kanji(c)
        if i == 0:
            current = c
            current_is_kanji = ck
        elif ck != current_is_kanji:
            segments.append((current, current_is_kanji))
            current = c
            current_is_kanji = ck
        else:
            current += c
    if current:
        segments.append((current, current_is_kanji))

    # 用非汉字部分定位汉字读音
    reading_remaining = reading

    for seg_idx, (seg_text, seg_is_kanji_flag) in enumerate(segments):
        if not seg_is_kanji_flag:
            hira = jaconv.kata2hira(seg_text)
            if reading_remaining.startswith(hira):
                reading_remaining = reading_remaining[len(hira):]
            elif len(seg_text) <= len(reading_remaining):
                reading_remaining = reading_remaining[len(seg_text):]
            for c in seg_text:
                result.append({"char": c, "reading": ""})
        else:
            # 找下一个非汉字部分
            next_non_kanji = ""
            for future_seg, future_is_kanji in segments[seg_idx+1:]:
                if not future_is_kanji:
                    next_non_kanji = jaconv.kata2hira(future_seg)
                    break

            if next_non_kanji and next_non_kanji in reading_remaining:
                idx = reading_remaining.index(next_non_kanji)
                kanji_reading = reading_remaining[:idx]
                reading_remaining = reading_remaining[idx:]
            else:
                kanji_reading = reading_remaining
                reading_remaining = ""

            # 分配给每个汉字
            if len(seg_text) == 1:
                result.append({"char": seg_text, "reading": kanji_reading})
            elif kanji_reading:
                chars_per = max(1, len(kanji_reading) // len(seg_text))
                remainder = len(kanji_reading) % len(seg_text)
                idx = 0
                for i, c in enumerate(seg_text):
                    take = chars_per + (1 if i < remainder else 0)
                    result.append({"char": c, "reading": kanji_reading[idx:idx+take]})
                    idx += take
            else:
                for c in seg_text:
                    result.append({"char": c, "reading": ""})

    return result


def annotate_line(text: str) -> list[dict]:
    """
    对一行歌词进行假名标注
    返回: [{char: str, reading: str}, ...]
    """
    tagger = get_tagger()
    if tagger is None:
        return [{"char": c, "reading": ""} for c in text]

    result = []
    words = tagger(text)

    for word in words:
        surface = word.surface
        if not surface:
            continue

        reading = get_reading(word)
        annotations = annotate_word(surface, reading)
        result.extend(annotations)

    return result


def process_lyrics(text: str, format: str = "plain") -> list[dict]:
    """
    处理歌词文本，返回带假名标注的行列表
    """
    lines = []

    if format == "lrc":
        lines = _parse_lrc(text)
    elif format == "ass":
        lines = _parse_ass(text)
    else:
        for line_text in text.strip().split("\n"):
            line_text = line_text.strip()
            if line_text:
                lines.append({
                    "text": line_text,
                    "start_time": None,
                    "end_time": None,
                })

    # 假名标注
    for line in lines:
        line["ruby"] = annotate_line(line["text"])

    return lines


def _parse_lrc(text: str) -> list[dict]:
    """解析 LRC 格式歌词"""
    lines = []
    lrc_pattern = re.compile(r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)')

    for raw_line in text.strip().split("\n"):
        match = lrc_pattern.match(raw_line.strip())
        if match:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            ms_str = match.group(3)
            ms = int(ms_str) * (10 if len(ms_str) == 2 else 1)
            start_time = minutes * 60 + seconds + ms / 1000.0
            line_text = match.group(4).strip()
            if line_text:
                lines.append({
                    "text": line_text,
                    "start_time": start_time,
                    "end_time": None,
                })

    for i in range(len(lines) - 1):
        lines[i]["end_time"] = lines[i+1]["start_time"]
    if lines:
        lines[-1]["end_time"] = lines[-1]["start_time"] + 5.0

    return lines


def _parse_ass(text: str) -> list[dict]:
    """简单解析 ASS Dialogue 行"""
    lines = []
    dialogue_pattern = re.compile(
        r'Dialogue:\s*\d+,(\d+):(\d+):(\d+\.\d+),(\d+):(\d+):(\d+\.\d+),.*?,,(.*)' 
    )

    for raw_line in text.strip().split("\n"):
        match = dialogue_pattern.match(raw_line.strip())
        if match:
            start_h, start_m, start_s = int(match.group(1)), int(match.group(2)), float(match.group(3))
            end_h, end_m, end_s = int(match.group(4)), int(match.group(5)), float(match.group(6))
            start_time = start_h * 3600 + start_m * 60 + start_s
            end_time = end_h * 3600 + end_m * 60 + end_s
            raw_text = match.group(7)
            clean_text = re.sub(r'\{[^}]*\}', '', raw_text).strip()
            if clean_text:
                lines.append({
                    "text": clean_text,
                    "start_time": start_time,
                    "end_time": end_time,
                })

    return lines
