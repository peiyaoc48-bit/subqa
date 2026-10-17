"""字幕读取：基于 pysubs2，支持 SRT / VTT / ASS 等格式。

自己只做两件事：
1. 统一成 Cue 结构，正文用 \\n 表示换行、格式标签统一保留为 ASS 风格（{\\i1}…{\\i0}），
   原文和译文用同一种表示，便于逐条对比；
2. 把 pysubs2 不友好的报错翻译成用户能看懂的提示，并自动识别 UTF-8 / GBK 编码。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pysubs2

TAG_RE = re.compile(r"\{\\[^}]*\}")  # ASS 风格的格式标签，SRT 的 <i> 读入后也会变成这种


class SubtitleError(ValueError):
    """字幕文件无法读取。"""


@dataclass(frozen=True)
class Cue:
    index: int        # 第几条（从 1 开始）
    start_ms: int
    end_ms: int
    text: str         # 含格式标签，换行为 \n
    plain: str        # 去掉格式标签后观众看到的文字

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    @property
    def lines(self) -> list[str]:
        return self.plain.split("\n")

    @property
    def tags(self) -> list[str]:
        return TAG_RE.findall(self.text)


def format_time(ms: int) -> str:
    h, rest = divmod(ms, 3_600_000)
    m, rest = divmod(rest, 60_000)
    s, ms = divmod(rest, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _to_cues(subs: pysubs2.SSAFile) -> list[Cue]:
    events = [e for e in subs if not e.is_comment]
    return [Cue(i, e.start, e.end, e.text.replace("\\N", "\n").replace("\\n", "\n"),
                e.plaintext.strip()) for i, e in enumerate(events, 1)]


def load(path: str | Path) -> list[Cue]:
    path = Path(path)
    if not path.exists():
        raise SubtitleError(f"找不到文件：{path}")
    if not path.read_bytes().strip(b" \t\r\n\xef\xbb\xbf"):
        raise SubtitleError(f"{path.name}：文件是空的，没有任何字幕")
    last_error = None
    for encoding in ("utf-8-sig", "gb18030"):  # 国内字幕文件常见 GBK 编码
        try:
            subs = pysubs2.load(str(path), encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
        except pysubs2.exceptions.FormatAutodetectionError:
            raise SubtitleError(f"{path.name}：无法识别字幕格式。常见原因是时间轴写错，"
                                "应为 00:00:01,000 --> 00:00:02,000") from None
        except Exception as e:  # pysubs2 的其他解析错误
            last_error = e
            break
    else:
        raise SubtitleError(f"{path.name}：无法识别文件编码，请转成 UTF-8")
    if last_error:
        raise SubtitleError(f"{path.name}：解析失败（{last_error}）")
    cues = _to_cues(subs)
    if not cues:
        raise SubtitleError(f"{path.name}：文件里没有任何字幕")
    return cues
