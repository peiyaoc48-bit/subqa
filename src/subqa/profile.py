"""质检规则的阈值配置。

默认值参考 Netflix 的英文字幕规范，每一项都写明来源和核实情况；
不同公司、不同平台规范不一样，用户可以用 --set 覆盖任意一项，比如 --set max_cps=17。
"""
from __future__ import annotations

from dataclasses import dataclass, fields, replace


@dataclass(frozen=True)
class Profile:
    # Netflix 拉丁字母语言字幕：每行最多 42 个字符（Netflix Backlot 帮助中心，已核实）
    max_chars_per_line: int = 42
    # 每条字幕最多 2 行（常见规范；Netflix 模板同为 2 行）
    max_lines: int = 2
    # 阅读速度上限：每秒字符数。成人节目常见取值 20、儿童节目 17
    # （来源为第三方整理，未能在 Netflix 官方页面核实，使用前请对照你所在平台的规范）
    max_cps: float = 20.0
    # 译文长度超过原文字数的多少倍视为输出失控（来自本项目的真实缺陷：62 字被扩写成 528 倍）
    max_length_ratio: float = 10.0
    # 字幕最短显示时长（毫秒），低于此值观众来不及看清
    min_duration_ms: int = 833

    @classmethod
    def with_overrides(cls, overrides: list[str]) -> "Profile":
        """把 ["max_cps=17", "max_lines=3"] 这样的字符串列表应用到默认配置上。"""
        types = {f.name: f.type for f in fields(cls)}
        values = {}
        for item in overrides:
            key, sep, raw = item.partition("=")
            key = key.strip()
            if not sep or key not in types:
                raise ValueError(f"无效的配置项 {item!r}，可用的有：{', '.join(types)}")
            try:
                values[key] = float(raw) if "float" in str(types[key]) else int(raw)
            except ValueError:
                raise ValueError(f"配置项 {key} 的值必须是数字，收到的是 {raw!r}") from None
        return replace(cls(), **values)
