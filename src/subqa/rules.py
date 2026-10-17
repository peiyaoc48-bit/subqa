"""质检规则。

每条规则都是一个函数：输入原文和译文字幕，返回发现的问题列表。
新增规则只需写一个函数并加进 RULES，报告、命令行都不用改。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from subqa.profile import Profile
from subqa.subtitle import Cue, format_time

CJK_RE = re.compile(r"[一-鿿㐀-䶿]")

ERROR, WARNING = "error", "warning"


@dataclass(frozen=True)
class Issue:
    rule: str          # 规则 id，比如 "cps"
    severity: str      # error：必须修；warning：建议修
    index: int | None  # 字幕序号；None 表示整个文件层面的问题
    message: str
    source: str = ""
    target: str = ""
    time: str = ""


def _issue(rule, severity, src: Cue | None, tgt: Cue | None, message) -> Issue:
    ref = tgt or src
    return Issue(rule, severity, ref.index if ref else None, message,
                 src.plain if src else "", tgt.plain if tgt else "",
                 f"{format_time(ref.start_ms)} --> {format_time(ref.end_ms)}" if ref else "")


# ---------- 结构 ----------

def check_structure(src: list[Cue], tgt: list[Cue], p: Profile, glossary) -> list[Issue]:
    """条数、时间轴必须和原文一致，否则字幕会错位。"""
    issues = []
    if len(src) != len(tgt):
        issues.append(Issue("structure", ERROR, None, f"条数不一致：原文 {len(src)} 条，译文 {len(tgt)} 条"))
    for s, t in zip(src, tgt):
        if (s.start_ms, s.end_ms) != (t.start_ms, t.end_ms):
            issues.append(_issue("structure", ERROR, s, t,
                                 f"时间轴被改动：原文 {format_time(s.start_ms)}，译文 {format_time(t.start_ms)}"))
    return issues


def check_overlap(src, tgt, p, glossary) -> list[Issue]:
    """时间轴倒置或与下一条重叠。"""
    issues = []
    for a, b in zip(tgt, tgt[1:]):
        if a.end_ms <= a.start_ms:
            issues.append(_issue("timing", ERROR, None, a, "结束时间早于或等于开始时间"))
        elif a.end_ms > b.start_ms:
            issues.append(_issue("timing", WARNING, None, a, f"和第 {b.index} 条时间重叠 {a.end_ms - b.start_ms} 毫秒"))
    return issues


# ---------- 内容 ----------

def check_empty(src, tgt, p, glossary) -> list[Issue]:
    return [_issue("empty", ERROR, s, t, "译文为空") for s, t in zip(src, tgt) if s.plain and not t.plain]


def check_untranslated(src, tgt, p, glossary) -> list[Issue]:
    """译文里残留中文，通常是漏译。"""
    issues = []
    for s, t in zip(src, tgt):
        left = CJK_RE.findall(t.plain)
        if left:
            issues.append(_issue("untranslated", ERROR, s, t, f"残留未翻译的中文：{''.join(left)[:20]}"))
    return issues


def check_length_ratio(src, tgt, p, glossary) -> list[Issue]:
    """译文比原文长太多，通常是大模型输出失控、重复生成。"""
    issues = []
    for s, t in zip(src, tgt):
        n = len(s.plain)
        if n and len(t.plain) / n > p.max_length_ratio:
            issues.append(_issue("length_ratio", ERROR, s, t,
                                 f"译文长度是原文的 {len(t.plain) / n:.0f} 倍，疑似输出失控"))
    return issues


TAG_NAMES = {"i": "斜体", "b": "粗体", "u": "下划线", "s": "删除线"}


def _describe(tags: list[str]) -> str:
    """把 {\\i1}{\\i0} 这样的标签转成"斜体"这样的说明。"""
    names = []
    for tag in tags:
        m = re.match(r"\{\\([a-z]+)1\}", tag)
        if m:
            names.append(TAG_NAMES.get(m.group(1), m.group(1)))
        elif not re.match(r"\{\\[a-z]+0\}", tag):
            names.append(tag)
    return "、".join(names) or "无格式"


def check_tags(src, tgt, p, glossary) -> list[Issue]:
    """<i>斜体</i> 等格式标签必须保留。"""
    issues = []
    for s, t in zip(src, tgt):
        a, b = s.tags, t.tags
        if a != b:
            issues.append(_issue("tags", ERROR, s, t, f"格式标签不一致：原文 {_describe(a)}，译文 {_describe(b)}"))
    return issues


# ---------- 可读性（观众来不来得及看）----------

def check_lines(src, tgt, p, glossary) -> list[Issue]:
    issues = []
    for s, t in zip(src, tgt):
        if len(t.lines) > p.max_lines:
            issues.append(_issue("lines", ERROR, s, t, f"共 {len(t.lines)} 行，超过上限 {p.max_lines} 行"))
        for line in t.lines:
            n = len(line)
            if n > p.max_chars_per_line:
                issues.append(_issue("line_length", WARNING, s, t, f"单行 {n} 个字符，超过上限 {p.max_chars_per_line}"))
                break
    return issues


def check_cps(src, tgt, p, glossary) -> list[Issue]:
    """阅读速度：字符数 / 显示秒数。太快观众读不完。"""
    issues = []
    for s, t in zip(src, tgt):
        seconds = t.duration_ms / 1000
        chars = len(t.plain.replace("\n", " "))
        if seconds > 0 and chars / seconds > p.max_cps:
            issues.append(_issue("cps", WARNING, s, t,
                                 f"阅读速度 {chars / seconds:.1f} 字符/秒，超过上限 {p.max_cps:g}"
                                 f"（{chars} 个字符只显示 {seconds:.1f} 秒）"))
    return issues


def check_duration(src, tgt, p, glossary) -> list[Issue]:
    return [_issue("duration", WARNING, s, t, f"只显示 {t.duration_ms} 毫秒，短于 {p.min_duration_ms} 毫秒")
            for s, t in zip(src, tgt) if 0 < t.duration_ms < p.min_duration_ms]


# ---------- 术语 ----------

def check_glossary(src, tgt, p, glossary: dict[str, list[str]]) -> list[Issue]:
    """原文出现术语表里的词，译文必须使用约定的译法（人名、地名、品牌、专有名词）。"""
    issues = []
    for s, t in zip(src, tgt):
        for zh, allowed in glossary.items():
            if zh in s.plain and not any(e.lower() in t.plain.lower() for e in allowed):
                issues.append(_issue("glossary", WARNING, s, t, f"术语「{zh}」应译为 {' / '.join(allowed)}"))
    return issues
