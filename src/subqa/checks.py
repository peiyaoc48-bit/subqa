"""规则注册表：所有检查项在这里登记，报告和命令行从这里读取。

新增一条规则：写一个函数 fn(src, tgt, profile, glossary) -> list[Issue]，加进 CHECKS 即可。
"""
from __future__ import annotations

from typing import Callable

from subqa import consistency as c
from subqa import rules as r
from subqa.profile import Profile
from subqa.rules import Issue
from subqa.subtitle import Cue

Check = Callable[[list[Cue], list[Cue], Profile, dict], list[Issue]]

# 规则 id → (检查函数, 分组, 说明)
CHECKS: dict[str, tuple[Check, str, str]] = {
    "structure": (r.check_structure, "格式", "条数、时间轴与原文一致"),
    "timing": (r.check_overlap, "格式", "时间轴不倒置、不重叠"),
    "tags": (r.check_tags, "格式", "格式标签（斜体等）保留"),
    "lines": (r.check_lines, "可读性", "行数、每行字符数符合规范"),
    "cps": (r.check_cps, "可读性", "阅读速度不超标"),
    "duration": (r.check_duration, "可读性", "显示时长足够"),
    "empty": (r.check_empty, "内容", "译文不为空"),
    "untranslated": (r.check_untranslated, "内容", "没有残留未翻译的中文"),
    "length_ratio": (r.check_length_ratio, "内容", "译文长度不失控"),
    "pronoun": (c.check_pronoun_gender, "一致性", "人称性别与原文一致（含省略主语时的上文）"),
    "name": (c.check_name_consistency, "一致性", "人名译法前后统一"),
    "glossary": (r.check_glossary, "一致性", "术语按术语表翻译"),
}


def run_all(src: list[Cue], tgt: list[Cue], profile: Profile | None = None,
            glossary: dict | None = None, skip: set[str] = frozenset()) -> list[Issue]:
    profile = profile or Profile()
    issues = []
    for rule_id, (fn, _, _) in CHECKS.items():
        if rule_id not in skip:
            issues.extend(fn(src, tgt, profile, glossary or {}))
    return sorted(issues, key=lambda i: (i.index is not None, i.index or 0, i.rule))
