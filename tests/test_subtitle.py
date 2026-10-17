"""字幕读取：真实世界里各种不规范的文件都要能读。"""
import pytest

from subqa.subtitle import SubtitleError, format_time, load

BASIC = "1\n00:00:01,000 --> 00:00:02,500\n你好\n\n2\n00:00:03,000 --> 00:00:04,000\n第一行\n第二行\n"


def test_basic(write_srt):
    cues = load(write_srt(BASIC))
    assert [c.index for c in cues] == [1, 2]
    assert (cues[0].start_ms, cues[0].end_ms, cues[0].duration_ms) == (1000, 2500, 1500)
    assert cues[1].lines == ["第一行", "第二行"]


@pytest.mark.parametrize("content, name, encoding", [
    ("﻿" + BASIC, "bom.srt", "utf-8"),                          # Windows 记事本的 BOM
    (BASIC.replace("\n", "\r\n"), "crlf.srt", "utf-8"),              # Windows 换行
    (BASIC.replace(",", "."), "dot.srt", "utf-8"),                   # 毫秒用点号
    (BASIC.replace("\n\n2", "\n\n\n\n2"), "gaps.srt", "utf-8"),     # 多余空行
    (BASIC, "gbk.srt", "gbk"),                                       # GBK 编码
], ids=["bom", "crlf", "dot-ms", "blank-lines", "gbk"])
def test_messy_files(write_srt, content, name, encoding):
    cues = load(write_srt(content, name, encoding))
    assert len(cues) == 2 and cues[0].plain == "你好" and cues[1].lines == ["第一行", "第二行"]


def test_vtt(write_srt):
    cues = load(write_srt("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n你好\n", "a.vtt"))
    assert cues[0].plain == "你好"


def test_tags_kept_and_stripped(write_srt):
    cue = load(write_srt("1\n00:00:01,000 --> 00:00:02,000\n<i>他在撒谎。</i>\n"))[0]
    assert cue.plain == "他在撒谎。" and len(cue.tags) == 2


@pytest.mark.parametrize("content, hint", [
    ("1\n00:00:01 --> 00:00:02\n缺毫秒\n", "时间轴"),
    ("", "没有任何字幕"),
])
def test_bad_files_give_readable_errors(write_srt, content, hint):
    with pytest.raises(SubtitleError, match=hint):
        load(write_srt(content))


def test_missing_file(tmp_path):
    with pytest.raises(SubtitleError, match="找不到文件"):
        load(tmp_path / "nope.srt")


def test_format_time():
    assert format_time(3_723_045) == "01:02:03,045"
