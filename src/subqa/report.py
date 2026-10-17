"""质检结果输出：终端文本、JSON（给 CI 和其他程序用）、HTML（发给同事看）。"""
from __future__ import annotations

import html
import json
import sys
from collections import Counter
from dataclasses import asdict

from subqa.checks import CHECKS
from subqa.rules import ERROR, WARNING, Issue

_COLOR = {ERROR: "\033[31m", WARNING: "\033[33m", "dim": "\033[2m", "bold": "\033[1m", "green": "\033[32m"}
_RESET = "\033[0m"
LABEL = {ERROR: "错误", WARNING: "警告"}


def _c(text: str, color: str, enabled: bool) -> str:
    return f"{_COLOR[color]}{text}{_RESET}" if enabled else text


def summary(issues: list[Issue]) -> dict:
    by_rule = Counter(i.rule for i in issues)
    return {
        "errors": sum(i.severity == ERROR for i in issues),
        "warnings": sum(i.severity == WARNING for i in issues),
        "by_rule": {rule: by_rule.get(rule, 0) for rule in CHECKS},
    }


# ---------- 质检 ----------

def text_report(issues: list[Issue], total: int, color: bool | None = None, limit: int = 50) -> str:
    color = sys.stdout.isatty() if color is None else color
    s = summary(issues)
    out = [_c(f"共 {total} 条字幕：{s['errors']} 个错误，{s['warnings']} 个警告", "bold", color), ""]
    group = None
    for rule, (_, grp, desc) in CHECKS.items():
        if grp != group:
            out.append(_c(f"[{grp}]", "dim", color))
            group = grp
        n = s["by_rule"][rule]
        mark = _c("✓", "green", color) if n == 0 else _c(f"✗ {n}", ERROR if any(i.rule == rule and i.severity == ERROR for i in issues) else WARNING, color)
        out.append(f"  {mark:<6} {desc}")
    if issues:
        out += ["", _c("问题明细", "bold", color)]
        for i in issues[:limit]:
            where = f"#{i.index}" if i.index is not None else "全文"
            out.append(f"  {_c(LABEL[i.severity], i.severity, color)} {where:<5} {i.message}")
            if i.source or i.target:
                out.append(_c(f"         原文：{i.source.replace(chr(10), ' / ')}", "dim", color))
                out.append(_c(f"         译文：{i.target.replace(chr(10), ' / ')}", "dim", color))
        if len(issues) > limit:
            out.append(f"  …… 还有 {len(issues) - limit} 个问题，用 --format html 查看完整报告")
    return "\n".join(out)


def json_report(issues: list[Issue], total: int, **extra) -> str:
    return json.dumps({"total": total, **summary(issues), **extra, "issues": [asdict(i) for i in issues]},
                      ensure_ascii=False, indent=2)


def html_report(issues: list[Issue], total: int, title: str) -> str:
    s = summary(issues)
    rows = "\n".join(
        f'<tr class="{i.severity}" data-rule="{i.rule}"><td>{i.index if i.index is not None else "全文"}</td>'
        f'<td><span class="pill {i.severity}">{LABEL[i.severity]}</span></td>'
        f'<td>{html.escape(CHECKS[i.rule][2] if i.rule in CHECKS else i.rule)}</td>'
        f'<td>{html.escape(i.message)}</td>'
        f'<td class="t">{html.escape(i.source).replace(chr(10), "<br>")}</td>'
        f'<td class="t">{html.escape(i.target).replace(chr(10), "<br>")}</td>'
        f'<td class="mono">{html.escape(i.time)}</td></tr>' for i in issues)
    checks = "".join(
        f'<li class="{"ok" if s["by_rule"][r] == 0 else "bad"}">{html.escape(g)} · {html.escape(d)}'
        f'<b>{s["by_rule"][r] or "✓"}</b></li>' for r, (_, g, d) in CHECKS.items())
    return f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>
<style>
:root{{--bg:#f7f8fa;--card:#fff;--fg:#1d2228;--muted:#69727d;--line:#dde1e6;--err:#c62828;--err-bg:#fdecea;--warn:#a05a00;--warn-bg:#fff4e0;--ok:#2e7d32}}
@media (prefers-color-scheme:dark){{:root{{--bg:#15181c;--card:#1d2127;--fg:#e4e7eb;--muted:#9aa3ad;--line:#2f353d;--err:#ff8a80;--err-bg:#3b1f1f;--warn:#ffcc80;--warn-bg:#3a2c16;--ok:#81c784}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}}
main{{max-width:1200px;margin:0 auto;padding:24px 16px}} h1{{font-size:20px;margin:0 0 4px}}
.sum{{color:var(--muted);margin-bottom:16px}} .sum b{{color:var(--fg)}}
ul.checks{{list-style:none;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:6px;margin:0 0 20px}}
ul.checks li{{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:6px 10px;display:flex;justify-content:space-between;gap:8px}}
ul.checks li.ok b{{color:var(--ok)}} ul.checks li.bad b{{color:var(--err)}}
.filters{{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap}} .filters button{{font:inherit;padding:4px 12px;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:999px;cursor:pointer}}
.filters button[aria-pressed=true]{{border-color:var(--fg);font-weight:600}}
.wrap{{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:8px}}
table{{border-collapse:collapse;width:100%;min-width:900px}} th,td{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
th{{font-size:12px;color:var(--muted);font-weight:600}} td.t{{max-width:260px}} .mono{{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:var(--muted);white-space:nowrap}}
.pill{{font-size:12px;padding:1px 8px;border-radius:999px;font-weight:600;white-space:nowrap}} .pill.error{{background:var(--err-bg);color:var(--err)}} .pill.warning{{background:var(--warn-bg);color:var(--warn)}}
footer{{color:var(--muted);font-size:12px;margin-top:16px}}
</style></head><body><main>
<h1>{html.escape(title)}</h1>
<p class="sum">共 <b>{total}</b> 条字幕：<b>{s['errors']}</b> 个错误，<b>{s['warnings']}</b> 个警告</p>
<ul class="checks">{checks}</ul>
<div class="filters"><button aria-pressed="true" data-f="all">全部 {len(issues)}</button>
<button aria-pressed="false" data-f="error">错误 {s['errors']}</button><button aria-pressed="false" data-f="warning">警告 {s['warnings']}</button></div>
<div class="wrap"><table><thead><tr><th>#</th><th>级别</th><th>检查项</th><th>问题</th><th>原文</th><th>译文</th><th>时间轴</th></tr></thead>
<tbody>{rows or '<tr><td colspan="7">没有发现问题</td></tr>'}</tbody></table></div>
<footer>由 SubQA 生成</footer></main>
<script>document.querySelectorAll('.filters button').forEach(b=>b.onclick=()=>{{
document.querySelectorAll('.filters button').forEach(x=>x.setAttribute('aria-pressed',x===b));
document.querySelectorAll('tbody tr[data-rule]').forEach(r=>r.hidden=b.dataset.f!=='all'&&!r.classList.contains(b.dataset.f));}});</script>
</body></html>"""


# ---------- 版本对比 ----------

def _key(i: Issue) -> tuple:
    return (i.index, i.rule)


def compare(old: list[Issue], new: list[Issue]) -> dict:
    """按（字幕序号, 规则）对比两个版本的问题：哪些修好了、哪些是新引入的。"""
    old_keys, new_keys = {_key(i) for i in old}, {_key(i) for i in new}
    return {
        "fixed": [i for i in old if _key(i) not in new_keys],
        "introduced": [i for i in new if _key(i) not in old_keys],
        "remaining": [i for i in new if _key(i) in old_keys],
    }


def compare_text(result: dict, old_name: str, new_name: str, changed: int, total: int,
                 color: bool | None = None) -> str:
    color = sys.stdout.isatty() if color is None else color
    fixed, intro, remain = result["fixed"], result["introduced"], result["remaining"]
    out = [_c(f"{old_name} → {new_name}：{changed}/{total} 条字幕译文有改动", "bold", color),
           f"  {_c(f'修复 {len(fixed)}', 'green', color)}　{_c(f'新引入 {len(intro)}', ERROR, color)}　仍存在 {len(remain)}", ""]
    for label, items, col in (("新引入的问题（回归）", intro, ERROR), ("已修复的问题", fixed, "green")):
        if items:
            out.append(_c(label, "bold", color))
            for i in items:
                out.append(f"  {_c(LABEL[i.severity], col if col == 'green' else i.severity, color)} "
                           f"#{i.index if i.index is not None else '全文'} {i.message}")
            out.append("")
    return "\n".join(out).rstrip()
