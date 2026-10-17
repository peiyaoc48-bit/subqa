"""命令行：退出码是给 CI 用的契约，必须稳定。"""
import json

from subqa.cli import main


def run(capsys, *args):
    code = main([str(a) for a in args])
    return code, capsys.readouterr()


def test_check_finds_known_problems(capsys, examples):
    code, out = run(capsys, "check", examples / "zh.srt", examples / "en_ai.srt",
                    "--glossary", examples / "glossary.csv", "--format", "json")
    report = json.loads(out.out)
    assert code == 1
    found = {(i["index"], i["rule"]) for i in report["issues"]}
    # 示例译文里埋的真实问题，一个都不能漏
    for expected in [(3, "pronoun"), (5, "tags"), (6, "name"), (7, "length_ratio"), (8, "untranslated")]:
        assert expected in found, expected


def test_clean_translation_passes(capsys, examples):
    code, out = run(capsys, "check", examples / "zh.srt", examples / "en_fixed.srt",
                    "--glossary", examples / "glossary.csv")
    assert code == 0 and "0 个错误，0 个警告" in out.out


def test_fail_on_levels(capsys, examples):
    args = ["check", examples / "zh.srt", examples / "en_ai.srt", "--skip", "tags,length_ratio,untranslated"]
    assert run(capsys, *args)[0] == 0                          # 只剩警告，默认不失败
    assert run(capsys, *args, "--fail-on", "warning")[0] == 1


def test_html_report(capsys, examples, tmp_path):
    out = tmp_path / "r.html"
    run(capsys, "check", examples / "zh.srt", examples / "en_ai.srt", "--format", "html", "-o", out)
    page = out.read_text(encoding="utf-8")
    assert "<table>" in page and "人名写法不一致" in page


def test_compare_detects_regression_direction(capsys, examples):
    zh, bad, good = examples / "zh.srt", examples / "en_ai.srt", examples / "en_fixed.srt"
    code, out = run(capsys, "compare", zh, bad, good)
    assert code == 0 and "新引入 0" in out.out           # 越改越好：通过
    code, out = run(capsys, "compare", zh, good, bad)
    assert code == 1 and "新引入的问题" in out.out        # 引入回归：拦下


def test_usage_errors_exit_2(capsys, examples, tmp_path):
    assert run(capsys, "check", examples / "zh.srt", tmp_path / "nope.srt")[0] == 2
    assert run(capsys, "check", examples / "zh.srt", examples / "en_ai.srt", "--skip", "nope")[0] == 2
    assert run(capsys, "check", examples / "zh.srt", examples / "en_ai.srt", "--set", "max_cps=abc")[0] == 2
