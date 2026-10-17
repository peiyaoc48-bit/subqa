"""每条规则：该报的要报，不该报的不能误报。"""
import pytest

from conftest import cue
from subqa import rules as r
from subqa.consistency import _pinyin_names, check_name_consistency, check_pronoun_gender
from subqa.profile import Profile

P = Profile()


def ids(issues):
    return [i.index for i in issues]


def test_structure_count_and_timing():
    src = [cue(1, "你好", 0, 1000), cue(2, "再见", 1000, 2000)]
    assert r.check_structure(src, [cue(1, "Hi", 0, 1000)], P, {})[0].message.startswith("条数不一致")
    shifted = [cue(1, "Hi", 0, 1000), cue(2, "Bye", 1500, 2000)]
    assert ids(r.check_structure(src, shifted, P, {})) == [2]
    assert r.check_structure(src, [cue(1, "Hi", 0, 1000), cue(2, "Bye", 1000, 2000)], P, {}) == []


def test_overlap_and_reversed():
    tgt = [cue(1, "a", 0, 1500), cue(2, "b", 1000, 2000), cue(3, "c", 3000, 2500), cue(4, "d", 4000, 5000)]
    found = {i.index: i.severity for i in r.check_overlap([], tgt, P, {})}
    assert found == {1: "warning", 3: "error"}


def test_untranslated_and_empty():
    src = [cue(1, "这个视频绝绝子"), cue(2, "你好")]
    tgt = [cue(1, "This video is 绝绝子"), cue(2, "")]
    assert ids(r.check_untranslated(src, tgt, P, {})) == [1]
    assert ids(r.check_empty(src, tgt, P, {})) == [2]


def test_length_ratio_catches_runaway_output():
    src = [cue(1, "呜呜呜"), cue(2, "嗯。")]
    tgt = [cue(1, "wah " * 20), cue(2, "Yeah.")]  # 正常的短句扩写（2 字 → 5 字符）不能误报
    assert ids(r.check_length_ratio(src, tgt, P, {})) == [1]


def test_tags():
    src = [cue(1, "{\\i1}他在撒谎。{\\i0}"), cue(2, "{\\i1}好{\\i0}")]
    tgt = [cue(1, "He's lying."), cue(2, "{\\i1}OK{\\i0}")]
    issues = r.check_tags(src, tgt, P, {})
    assert ids(issues) == [1] and "斜体" in issues[0].message


def test_lines_and_line_length():
    src = [cue(1, "x"), cue(2, "x")]
    tgt = [cue(1, "a\nb\nc"), cue(2, "x" * 43)]
    found = {(i.index, i.rule) for i in r.check_lines(src, tgt, P, {})}
    assert found == {(1, "lines"), (2, "line_length")}


def test_cps_uses_display_time():
    src = [cue(1, "x"), cue(2, "x")]
    tgt = [cue(1, "x" * 30, 0, 1000), cue(2, "x" * 30, 0, 2000)]   # 30 字/秒 vs 15 字/秒
    assert ids(r.check_cps(src, tgt, P, {})) == [1]
    assert r.check_cps(src, tgt, Profile.with_overrides(["max_cps=40"]), {}) == []


def test_glossary_allows_alternatives():
    src = [cue(1, "绝绝子"), cue(2, "绝绝子")]
    tgt = [cue(1, "That's awesome"), cue(2, "That's so good")]
    assert ids(r.check_glossary(src, tgt, P, {"绝绝子": ["amazing", "awesome"]})) == [2]


# ---------- 一致性：本工具区别于格式检查器的核心 ----------

def test_pronoun_in_same_cue():
    src = [cue(1, "她今天不来了"), cue(2, "他今天不来了")]
    tgt = [cue(1, "He isn't coming today"), cue(2, "She isn't coming today")]
    assert ids(check_pronoun_gender(src, tgt, P, {})) == [1, 2]


def test_pronoun_from_context_when_subject_omitted():
    """真实缺陷：上文"我妈打电话来"，下一句省略主语，译文却写 He said。"""
    src = [cue(1, "我妈刚给我打了个电话。"), cue(2, "说今晚不回来吃饭了。")]
    wrong = [cue(1, "My mom just called me."), cue(2, "He said he won't be home.")]
    right = [cue(1, "My mom just called me."), cue(2, "She said she won't be home.")]
    issues = check_pronoun_gender(src, wrong, P, {})
    assert ids(issues) == [2] and "第 1 条" in issues[0].message
    assert check_pronoun_gender(src, right, P, {}) == []


@pytest.mark.parametrize("zh, en", [
    ("他们都走了", "They all left, and he stayed"),      # "他们"不表示单个男性
    ("我妈和我爸都来了", "She and he both came"),         # 男女都有，无法判断
    ("今天天气很好", "He says it's a nice day"),          # 原文和上文都没有性别线索
])
def test_pronoun_no_false_positive(zh, en):
    assert check_pronoun_gender([cue(1, zh)], [cue(1, en)], P, {}) == []


def test_pinyin_name_detection():
    assert _pinyin_names("Zhang Wei, go tell Li Na.") == ["Zhang Wei", "Li Na"]
    assert _pinyin_names("Ma Yun founded it") == ["Ma Yun"]
    assert _pinyin_names("Let's Go home. Hello World. Long Time no see") == []


def test_name_order_and_case_inconsistency():
    src = [cue(i, "x") for i in (1, 2, 3)]
    tgt = [cue(1, "Zhang Wei, wait."), cue(2, "Wei Zhang left."), cue(3, "Zhang wei is back.")]
    assert ids(check_name_consistency(src, tgt, P, {})) == [2, 3]


def test_profile_overrides():
    assert Profile.with_overrides(["max_cps=17", "max_lines=3"]).max_cps == 17
    with pytest.raises(ValueError, match="无效的配置项"):
        Profile.with_overrides(["nope=1"])
    with pytest.raises(ValueError, match="必须是数字"):
        Profile.with_overrides(["max_cps=abc"])
