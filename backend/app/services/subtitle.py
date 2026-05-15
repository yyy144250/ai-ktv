"""
ASS 字幕生成服务
生成带振り仮名 + KTV 逐字变色效果的 ASS 字幕文件
"""

from pathlib import Path
from typing import Optional


# 配色方案
STYLES = {
    "classic_blue": {
        "highlight": "&H00FFBF00&",   # 亮蓝 (BGR)
        "normal": "&H00FFFFFF&",       # 白色
        "furigana": "&H00AAAAAA&",    # 灰色
        "outline": "&H00000000&",     # 黑色描边
    },
    "pink": {
        "highlight": "&H00B469FF&",   # 粉红 (BGR)
        "normal": "&H00FFFFFF&",
        "furigana": "&H00CCAAFF&",
        "outline": "&H00000000&",
    },
    "gold": {
        "highlight": "&H0000D7FF&",   # 金色 (BGR)
        "normal": "&H00FFFFFF&",
        "furigana": "&H008BECFF&",
        "outline": "&H00000000&",
    },
}


def generate_ass_subtitle(
    lines: list[dict],
    output_path: Path,
    video_width: int = 1920,
    video_height: int = 1080,
    style: str = "classic_blue",
    font_size: int = 48,
    furigana_size: int = 24,
):
    """
    生成 ASS 字幕文件

    Args:
        lines: 歌词行 [{text, ruby, start_time, end_time, words}, ...]
        output_path: 输出文件路径
        video_width: 视频宽度
        video_height: 视频高度
        style: 配色方案名
        font_size: 主字幕字号
        furigana_size: 假名字号
    """
    colors = STYLES.get(style, STYLES["classic_blue"])

    # ASS 文件头
    header = _generate_header(video_width, video_height, font_size, furigana_size, colors)

    # 生成事件行
    events = []
    for line in lines:
        if not line.get("start_time") or not line.get("end_time"):
            continue

        start = _format_time(line["start_time"])
        end = _format_time(line["end_time"])
        ruby_data = line.get("ruby", [])
        words = line.get("words", [])

        # 生成假名行 (在主字幕上方)
        furigana_text = _build_furigana_line(ruby_data)
        if furigana_text.strip():
            events.append(
                f"Dialogue: 0,{start},{end},Furigana,,0,0,0,,{furigana_text}"
            )

        # 生成主字幕行 (带 KTV 逐字变色)
        if words:
            main_text = _build_karaoke_line(words, line["start_time"], colors)
        else:
            main_text = _build_simple_line(line["text"], colors)

        events.append(
            f"Dialogue: 1,{start},{end},Main,,0,0,0,,{main_text}"
        )

    # 写入文件
    content = header + "\n[Events]\n"
    content += "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    content += "\n".join(events) + "\n"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8-sig")


def _generate_header(
    width: int, height: int,
    font_size: int, furigana_size: int,
    colors: dict
) -> str:
    """生成 ASS 文件头"""
    margin_v = 60  # 底部边距

    return f"""[Script Info]
Title: AI-KTV Subtitle
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,Noto Sans JP,{font_size},{colors['normal']},{colors['highlight']},{colors['outline']},&H80000000&,-1,0,0,0,100,100,2,0,1,3,1,2,20,20,{margin_v},1
Style: Furigana,Noto Sans JP,{furigana_size},{colors['furigana']},&H00000000&,{colors['outline']},&H80000000&,0,0,0,0,100,100,0,0,1,2,0,2,20,20,{margin_v + font_size + 10},1

"""


def _format_time(seconds: float) -> str:
    """将秒数转为 ASS 时间格式 H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _build_furigana_line(ruby_data: list[dict]) -> str:
    """
    构建假名行文本
    只为有假名标注的汉字显示对应假名，其他位置用空格占位
    """
    parts = []
    for item in ruby_data:
        char = item.get("char", "")
        reading = item.get("reading", "")
        if reading:
            # 有假名标注：显示假名
            parts.append(reading)
        else:
            # 无假名：用全角空格占位，保持对齐
            parts.append("　" * max(1, len(char)))

    return "".join(parts)


def _build_karaoke_line(words: list[dict], line_start: float, colors: dict) -> str:
    """
    构建带 KTV 逐字变色的主字幕行
    使用 ASS 的 \\k 标签实现逐字高亮
    """
    parts = []

    for word in words:
        text = word.get("text", "")
        word_start = word.get("start", line_start)
        word_end = word.get("end", word_start + 0.5)

        # \\k 的时间单位是 centiseconds (1/100 秒)
        duration_cs = int((word_end - word_start) * 100)
        duration_cs = max(1, duration_cs)  # 至少 1cs

        parts.append(f"{{\\kf{duration_cs}}}{text}")

    return "".join(parts)


def _build_simple_line(text: str, colors: dict) -> str:
    """无逐字时间戳时的简单行"""
    return text
