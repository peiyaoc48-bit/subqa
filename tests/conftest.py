from pathlib import Path

import pytest

from subqa.subtitle import Cue

EXAMPLES = Path(__file__).parent.parent / "examples"


def cue(index, text, start=0, end=2000):
    """测试用的快捷构造：只关心文字时不用写时间轴。"""
    import re

    plain = re.sub(r"\{\\[^}]*\}", "", text)
    return Cue(index, start, end, text, plain)


@pytest.fixture
def examples():
    return EXAMPLES


@pytest.fixture
def write_srt(tmp_path):
    """把字符串写成字幕文件，返回路径；encoding 可以测 GBK 等编码。"""
    def _write(content: str, name="a.srt", encoding="utf-8"):
        path = tmp_path / name
        path.write_bytes(content.encode(encoding))
        return path
    return _write
