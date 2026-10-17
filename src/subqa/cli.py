"""命令行入口。

  subqa check 原文.srt 译文.srt [--glossary 术语表.csv] [--format text|json|html] [-o 输出文件]
  subqa compare 原文.srt 旧译文.srt 新译文.srt     # 换了 Prompt / 翻译供应商后，哪些变好了、哪些变差了

退出码：0 通过；1 发现错误（或 compare 时新引入了错误）；2 用法或文件错误。
可以直接放进 CI：译文质检不通过就阻止合并。
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from subqa import __version__
from subqa.checks import CHECKS, run_all
from subqa.profile import Profile
from subqa.report import compare, compare_text, html_report, json_report, text_report
from subqa.rules import ERROR, WARNING
from subqa.subtitle import SubtitleError, load


def load_glossary(path: str | None) -> dict[str, list[str]]:
    """CSV：第一列中文，第二列英文译法（多个用 | 分隔）；第一行是表头。"""
    if not path:
        return {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))[1:]
    return {r[0].strip(): [e.strip() for e in r[1].split("|") if e.strip()] for r in rows if len(r) >= 2 and r[0].strip()}


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--glossary", help="术语表 CSV：中文,英文译法（多个用 | 分隔）")
    p.add_argument("--set", action="append", default=[], metavar="项=值",
                   help="覆盖规则阈值，可多次使用，如 --set max_cps=17 --set max_chars_per_line=37")
    p.add_argument("--skip", default="", help=f"跳过的检查项，逗号分隔。可选：{','.join(CHECKS)}")
    p.add_argument("--fail-on", choices=[ERROR, WARNING, "never"], default=ERROR,
                   help="出现哪一级问题时退出码为 1（默认 error）")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="subqa", description="中译英 AI 字幕质检")
    parser.add_argument("--version", action="version", version=f"subqa {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="质检一份译文")
    c.add_argument("source", help="中文原文字幕（SRT / VTT / ASS）")
    c.add_argument("target", help="英文译文字幕")
    c.add_argument("--format", choices=["text", "json", "html"], default="text")
    c.add_argument("-o", "--output", help="把报告写入文件（html 格式默认写入 subqa-report.html）")
    _common(c)

    m = sub.add_parser("compare", help="对比同一原文的两版译文")
    m.add_argument("source")
    m.add_argument("old", help="旧版译文")
    m.add_argument("new", help="新版译文")
    m.add_argument("--format", choices=["text", "json"], default="text")
    _common(m)
    return parser


def _failed(issues, level: str) -> bool:
    if level == "never":
        return False
    return any(i.severity == ERROR or (level == WARNING and i.severity == WARNING) for i in issues)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        profile = Profile.with_overrides(args.set)
        glossary = load_glossary(args.glossary)
        skip = {s.strip() for s in args.skip.split(",") if s.strip()}
        unknown = skip - set(CHECKS)
        if unknown:
            raise ValueError(f"未知的检查项：{', '.join(sorted(unknown))}")
        src = load(args.source)

        if args.command == "check":
            tgt = load(args.target)
            issues = run_all(src, tgt, profile, glossary, skip)
            if args.format == "json":
                report = json_report(issues, len(src), source=args.source, target=args.target)
            elif args.format == "html":
                report = html_report(issues, len(src), f"字幕质检报告 · {Path(args.target).name}")
                args.output = args.output or "subqa-report.html"
            else:
                report = text_report(issues, len(src))
            if args.output:
                Path(args.output).write_text(report, encoding="utf-8")
                print(f"报告已写入 {args.output}", file=sys.stderr)
            else:
                print(report)
            return 1 if _failed(issues, args.fail_on) else 0

        old, new = load(args.old), load(args.new)
        old_issues = run_all(src, old, profile, glossary, skip)
        new_issues = run_all(src, new, profile, glossary, skip)
        result = compare(old_issues, new_issues)
        changed = sum(a.text != b.text for a, b in zip(old, new))
        if args.format == "json":
            print(json_report(new_issues, len(src), changed=changed,
                              fixed=[i.__dict__ for i in result["fixed"]],
                              introduced=[i.__dict__ for i in result["introduced"]]))
        else:
            print(compare_text(result, Path(args.old).name, Path(args.new).name, changed, len(src)))
        # 对比模式只关心"新引入"的问题：旧问题没修完不算失败，引入新问题才算回归
        return 1 if _failed(result["introduced"], args.fail_on) else 0

    except (SubtitleError, ValueError, OSError) as e:
        print(f"subqa：{e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
