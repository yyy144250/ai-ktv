"""
振り仮名(假名标注)服务
使用 fugashi + unidic-lite 对日语汉字自动标注假名读音
"""

from app.services._furigana_impl import (
    annotate_line,
    process_lyrics,
    is_kanji,
    contains_kanji,
)

__all__ = ["annotate_line", "process_lyrics", "is_kanji", "contains_kanji"]
