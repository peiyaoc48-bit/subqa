"""跨条一致性检查：对照中文原文，发现格式检查器发现不了的语义错误。

1. 人称性别：原文是"她 / 妈妈 / 姐姐"，译文却用 he / him / his（或反过来）。
   中文口语常省略主语，所以也看前两条原文：上文说"我妈打电话来"，
   这一句"说今晚不回来吃饭了"的译文就不该是 He said…
2. 人名译法：同一个人名前后译法不同（Zhang Wei / Wei Zhang / Zhang wei）。

都是规则实现，不调用大模型：快、零成本、结果确定，适合每次提交都在 CI 里跑。
规则只能发现"可疑"之处，所以都标为 warning，由人工确认。
"""
from __future__ import annotations

import re
from collections import defaultdict

from subqa.profile import Profile
from subqa.rules import WARNING, _issue, Issue
from subqa.subtitle import Cue

FEMALE_ZH = ["她", "妈", "母亲", "姐", "妹", "奶奶", "姥姥", "外婆", "阿姨", "姑姑", "婶", "女儿",
             "老婆", "妻子", "媳妇", "女朋友", "女友", "小姐", "女士", "闺蜜", "大妈", "公主", "皇后", "王妃"]
MALE_ZH = ["他", "爸", "父亲", "哥", "弟", "爷爷", "姥爷", "外公", "叔", "舅", "伯", "儿子",
           "老公", "丈夫", "男朋友", "男友", "先生", "兄弟", "大爷", "王子", "皇上", "王爷"]
# "他们 / 她们 / 其他 / 吉他" 等不表示单个人的性别，先剔除再判断
NOT_GENDER = re.compile(r"他们|她们|其他|其它|吉他|他人|他乡|他日|姐妹们|兄弟们")

FEMALE_EN = re.compile(r"\b(she|her|hers|herself)\b", re.I)
MALE_EN = re.compile(r"\b(he|him|his|himself)\b", re.I)

CONTEXT_CUES = 2  # 主语省略时往前看几条


def _gender_zh(text: str) -> str | None:
    text = NOT_GENDER.sub("", text)
    f = any(w in text for w in FEMALE_ZH)
    m = any(w in text for w in MALE_ZH)
    return "female" if f and not m else "male" if m and not f else None


def check_pronoun_gender(src: list[Cue], tgt: list[Cue], p: Profile, glossary) -> list[Issue]:
    issues = []
    for i, (s, t) in enumerate(zip(src, tgt)):
        has_f, has_m = bool(FEMALE_EN.search(t.plain)), bool(MALE_EN.search(t.plain))
        if has_f == has_m:  # 译文没有人称代词，或男女都有（多人对话），无法判断
            continue
        expected, where = _gender_zh(s.plain), "本句"
        if expected is None:  # 本句没有性别线索，可能是省略主语，看前几条
            for back in range(1, CONTEXT_CUES + 1):
                if i - back >= 0 and (g := _gender_zh(src[i - back].plain)):
                    expected, where = g, f"第 {src[i - back].index} 条"
                    break
        if expected == "female" and has_m:
            issues.append(_issue("pronoun", WARNING, s, t, f"原文{where}指向女性，译文却用了 he / him / his"))
        elif expected == "male" and has_f:
            issues.append(_issue("pronoun", WARNING, s, t, f"原文{where}指向男性，译文却用了 she / her"))
    return issues


# 拼音音节：声母（可选）+ 韵母；名字部分允许 1-2 个音节（Wei / Xiaoming）
_SYLLABLE = (r"(?:zh|ch|sh|[bpmfdtnlgkhjqxrzcsyw])?"
             r"(?:iang|iong|uang|ueng|ang|eng|ing|ong|ian|iao|uai|uan|ai|ei|ao|ou|an|en|er|in|un|"
             r"ia|ie|iu|ua|uo|ui|ue|a|o|e|i|u|v)")
PINYIN_WORD = re.compile(rf"(?:{_SYLLABLE}){{1,2}}", re.I)
# 常见姓氏的拼音：两个词里至少一个是姓氏，才认为是人名，避免把普通英文词组当成人名
SURNAMES = set("""wang li zhang liu chen yang huang zhao wu zhou xu sun ma zhu hu guo he lin gao luo
zheng liang xie song tang han feng deng cao peng zeng xiao tian dong pan yuan cai jiang yu du ye cheng
wei su lu ding ren shen yao jin fu fan fang shi tan hou qin bai cui kang mo jia qiu xiong meng qian""".split())
# 合法拼音但常见的英文单词，不当作人名
ENGLISH = set("he she we me hi oh an in on no so go a i long hang men ban bin pan fan man tan".split())
PAIR_RE = re.compile(r"\b([A-Z][a-z]{0,8})\s+([A-Za-z][a-z]{0,8})\b")


def _is_name_part(word: str) -> bool:
    return bool(PINYIN_WORD.fullmatch(word)) and word.lower() not in ENGLISH


def _pinyin_names(text: str) -> list[str]:
    """找出译文里形如 "Zhang Wei" / "Lin Xiaoming" 的拼音人名。"""
    names = []
    for a, b in PAIR_RE.findall(text):
        if _is_name_part(a) and _is_name_part(b) and (a.lower() in SURNAMES or b.lower() in SURNAMES):
            names.append(f"{a} {b}")
    return names


def check_name_consistency(src: list[Cue], tgt: list[Cue], p: Profile, glossary) -> list[Issue]:
    """同一个名字出现不同写法：姓名顺序颠倒（Zhang Wei / Wei Zhang），或大小写不同（Zhang wei）。"""
    seen: dict[frozenset, dict[str, tuple[Cue, Cue]]] = defaultdict(dict)
    for s, t in zip(src, tgt):
        for name in _pinyin_names(t.plain):
            seen[frozenset(name.lower().split())].setdefault(name, (s, t))
    issues = []
    for variants in seen.values():
        if len(variants) > 1:
            first, *others = list(variants)
            for name in others:
                s, t = variants[name]
                issues.append(_issue("name", WARNING, s, t,
                                     f"人名写法不一致：此处为「{name}」，第 {variants[first][1].index} 条为「{first}」"))
    return issues
