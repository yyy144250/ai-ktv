"""
ASS 字幕生成服务
生成带振り仮名 + KTV 逐字变色效果的 ASS 字幕文件

假名对齐方案：
  Furigana style 使用和 Main style 完全相同的 Fontsize 和 Spacing，
  这样两行有完全相同的字符布局宽度。
  假名行每个位置输出恰好1个字符：
  - 无假名 → 全角空格（宽度=font_size，与主行字符等宽）
  - 单字假名 → 直接输出假名（宽度=font_size，与主行字符等宽）
  - 多字假名 → 用小字号显示，但占一个字宽（不可能严格做到）

  实际最佳方案：
  Furigana style 用相同 Fontsize，但通过 ScaleY 缩小高度让视觉上小一些。
  对于多字符假名，用 \fscx 压缩到一个字宽内。
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

# 主行底部边距
MARGIN_V = 60


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

        # 生成假名行
        furigana_text = _build_furigana_line(ruby_data, font_size, furigana_size)
        if furigana_text:
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
    """
    生成 ASS 文件头
    
    关键：Furigana style 使用和 Main style 相同的 Fontsize 和 Spacing，
    通过 ScaleX/ScaleY 缩小视觉大小，但字符占位宽度由 Fontsize 决定，
    所以两行天然逐字对齐。
    """
    # 假名行只缩小高度(ScaleY)，不缩小宽度(ScaleX=100)
    # 这样字符的 advance width 和主行完全一致，天然逐字对齐
    scale_y = int(furigana_size / font_size * 100)  # 50%
    
    # Furigana MarginV：使假名行底边在主行顶边上方
    furigana_margin_v = MARGIN_V + font_size + 4

    return f"""[Script Info]
Title: AI-KTV Subtitle
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,Noto Sans JP,{font_size},{colors['normal']},{colors['highlight']},{colors['outline']},&H80000000&,-1,0,0,0,100,100,2,0,1,3,1,2,20,20,{MARGIN_V},1
Style: Furigana,Noto Sans JP,{font_size},{colors['furigana']},&H00000000&,{colors['outline']},&H80000000&,0,0,0,0,100,{scale_y},2,0,1,1,0,2,20,20,{furigana_margin_v},1

"""


def _format_time(seconds: float) -> str:
    """将秒数转为 ASS 时间格式 H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _build_furigana_line(ruby_data: list[dict], font_size: int, furigana_size: int) -> str:
    """
    构建假名行文本。
    
    Furigana style: Fontsize=font_size, ScaleX=100, ScaleY=50%, Spacing=2
    和 Main style 完全相同的字符占位宽度（advance width = font_size）。
    
    规则（每个主行字符对应假名行的一个字符位）：
    - 无假名 → 全角空格（占一个字宽，天然对齐）
    - 单字假名 → 直接输出（占一个字宽，天然对齐）
    - 多字假名（如 かぜ）→ 用 \\fscx + \\fsp0 压缩到一个字宽内
    
    因为 ScaleX=100，单字符的视觉宽度和主行一样大。
    假名看起来高度小（ScaleY=50%）但宽度正常，这是合理的。
    """
    if not ruby_data:
        return ""

    has_furigana = any(item.get("reading") for item in ruby_data)
    if not has_furigana:
        return ""

    parts = []
    for item in ruby_data:
        reading = item.get("reading", "")

        if not reading:
            # 无假名：全角空格占位（宽度 = font_size = 主行字符宽度）
            parts.append("　")
        elif len(reading) == 1:
            # 单字假名：占位宽度 = font_size = 主行字符宽度，完美对齐
            parts.append(reading)
        else:
            # 多字假名：N个字符需要挤在1个字宽(font_size)内
            # \fscx 是绝对覆盖，字符宽度 = fontsize * fscx/100
            # N个字符总宽 = N * fontsize * fscx/100（fsp=0时无间距）
            # 目标 = fontsize → fscx = 100/N
            n = len(reading)
            fscx = int(100 / n)
            parts.append(f"{{\\fsp0\\fscx{fscx}}}{reading}{{\\fsp2\\fscx100}}")

    result = "".join(parts)

    # 检查是否实质上只有空格
    clean = result.replace("　", "")
    # 去掉 ASS 标签后检查
    import re
    clean = re.sub(r'\{[^}]*\}', '', clean)
    if not clean.strip():
        return ""

    return result


def _build_karaoke_line(words: list[dict], line_start: float, colors: dict) -> str:
    """
    构建带 KTV 逐字变色的主字幕行
    使用 ASS 的 \\kf 标签实现逐字高亮
    """
    parts = []

    for word in words:
        text = word.get("text", "")
        word_start = word.get("start", line_start)
        word_end = word.get("end", word_start + 0.5)

        duration_cs = int((word_end - word_start) * 100)
        duration_cs = max(1, duration_cs)

        parts.append(f"{{\\kf{duration_cs}}}{text}")

    return "".join(parts)


def _build_simple_line(text: str, colors: dict) -> str:
    """无逐字时间戳时的简单行"""
    return text
