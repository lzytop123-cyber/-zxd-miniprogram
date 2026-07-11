"""从团购/卡名解析周期卡连续可用天数（建议值与旧卡修复兜底）。"""
from __future__ import annotations

import re


def _normalize_name(name: str | None) -> str:
    return (name or "").replace(" ", "").replace("　", "")


def parse_pass_days_from_name(name: str | None) -> int | None:
    """
    解析名称中的连续自然日数。
    例：9月卡→270、双月卡→60、90天卡→90。
    无匹配返回 None（由调用方使用 reward_value / 默认值）。
    """
    text = _normalize_name(name)
    if not text:
        return None
    if re.search(r"双月|两个月|2个月", text):
        return 60
    month_match = re.search(r"(\d+)个?月", text)
    if month_match:
        months = int(month_match.group(1))
        if months > 0:
            return months * 30
    week_match = re.search(r"(\d+)个?周", text)
    if week_match:
        weeks = int(week_match.group(1))
        if weeks > 0:
            return weeks * 7
    day_match = re.search(r"(\d+)天", text)
    if day_match:
        days = int(day_match.group(1))
        if days > 1:
            return days
    return None
