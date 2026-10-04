"""后台店长模块权限目录与 API 路径映射。"""

from __future__ import annotations

import re
from typing import Callable

STORE_DEFAULT_PERMISSIONS = [
    "dashboard",
    "receipts",
    "live_board",
    "stores",
    "calendar",
    "pricing",
    "seats",
    "reservations",
    "locks",
    "door_logs",
    "card_orders",
    "period_cards",
    "deal_mappings",
    "exchange",
]

EXTENDED_PERMISSIONS = [
    "admins",
    "pay_accounts",
    "users",
    "wallet_logs",
    "point_logs",
    "invites",
    "coupons",
    "banners",
    "announcements",
    "notifications",
    "contact",
    "booking_setting",
    "study",
    "knowledge",
    "wrongbook",
    "market",
    "system",
    "operation_logs",
]

ALL_PERMISSIONS = STORE_DEFAULT_PERMISSIONS + EXTENDED_PERMISSIONS

PathRule = tuple[str | Callable[[str], bool], str]

_STORE_ID = r"\d+"

PATH_RULES: list[PathRule] = [
    (lambda p: bool(re.match(rf"^/api/admin/stores/{_STORE_ID}/pricing/copy-to", p)), "pricing"),
    ("/api/admin/stores/upload-cover", "stores"),
    (lambda p: bool(re.match(rf"^/api/admin/stores/{_STORE_ID}/live-board", p)), "live_board"),
    (lambda p: bool(re.match(rf"^/api/admin/stores/{_STORE_ID}/expiring-cards", p)), "live_board"),
    (lambda p: bool(re.match(rf"^/api/admin/stores/{_STORE_ID}/calendar", p)), "calendar"),
    (lambda p: bool(re.match(rf"^/api/admin/stores/{_STORE_ID}/seat-map", p)), "seats"),
    (lambda p: bool(re.match(rf"^/api/admin/stores/{_STORE_ID}/zones", p)), "seats"),
    (lambda p: bool(re.match(rf"^/api/admin/stores/{_STORE_ID}/seats", p)), "seats"),
    (lambda p: bool(re.match(rf"^/api/admin/stores/{_STORE_ID}/ensure-seats", p)), "seats"),
    (lambda p: bool(re.match(rf"^/api/admin/stores/{_STORE_ID}/pricing", p)), "pricing"),
    ("/api/admin/stats/todos", "dashboard"),
    ("/api/admin/stats/revenue", "dashboard"),
    ("/api/admin/stats/verify-by-source", "dashboard"),
    ("/api/admin/stats", "dashboard"),
    ("/api/admin/deal-mappings/pending", "deal_mappings"),
    ("/api/admin/deal-mappings/templates", "deal_mappings"),
    ("/api/admin/deal-mappings/import-templates", "deal_mappings"),
    ("/api/admin/deal-mappings", "deal_mappings"),
    ("/api/admin/export/wallet-logs", "wallet_logs"),
    ("/api/admin/export/reservations", "reservations"),
    ("/api/admin/export/study-stats", "study"),
    ("/api/admin/system/status", "system"),
    ("/api/admin/system/migrate", "system"),
    ("/api/admin/system/coupon", "coupons"),
    ("/api/admin/assistant", "study"),
    ("/api/admin/receipts", "receipts"),
    ("/api/admin/reservations", "reservations"),
    ("/api/admin/seats", "seats"),
    ("/api/admin/pricing", "pricing"),
    ("/api/admin/card-purchase-orders", "card_orders"),
    ("/api/admin/period-cards", "period_cards"),
    ("/api/admin/exchange-records", "exchange"),
    ("/api/admin/wallet-logs", "wallet_logs"),
    ("/api/admin/point-logs", "point_logs"),
    ("/api/admin/invites", "invites"),
    ("/api/admin/coupons", "coupons"),
    ("/api/admin/banners", "banners"),
    ("/api/admin/announcements", "announcements"),
    ("/api/admin/notifications", "notifications"),
    ("/api/admin/contact-setting", "contact"),
    ("/api/admin/booking-setting", "booking_setting"),
    ("/api/admin/study", "study"),
    ("/api/admin/knowledge", "knowledge"),
    ("/api/admin/wrongbook", "wrongbook"),
    ("/api/admin/market", "market"),
    ("/api/admin/operation-logs", "operation_logs"),
    ("/api/admin/admins", "admins"),
    ("/api/admin/pay-accounts", "pay_accounts"),
    ("/api/admin/users", "users"),
    ("/api/admin/locks", "locks"),
    ("/api/admin/door-logs", "door_logs"),
    ("/api/admin/stores", "stores"),
]

_ALWAYS_ALLOWED_PREFIXES = ("/api/admin/login", "/api/admin/me")


def _path_matches(path: str, prefix: str) -> bool:
    if path == prefix:
        return True
    return path.startswith(prefix + "/")


def _rule_matches(path: str, rule: str | Callable[[str], bool]) -> bool:
    if callable(rule):
        return rule(path)
    return _path_matches(path, rule)


def normalize_permissions(role: str, raw: list[str] | None) -> list[str]:
    if role == "hq":
        return list(ALL_PERMISSIONS)
    if raw is None:
        return list(STORE_DEFAULT_PERMISSIONS)
    allowed = set(raw)
    return [key for key in ALL_PERMISSIONS if key in allowed]


def has_permission(admin, key: str) -> bool:
    role = getattr(admin, "role", None)
    raw = getattr(admin, "permissions", None)
    return key in normalize_permissions(role, raw)


def module_for_admin_path(method: str, path: str) -> str | None:
    del method  # reserved for future method-specific rules
    for prefix in _ALWAYS_ALLOWED_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return None
    for rule, module_key in PATH_RULES:
        if _rule_matches(path, rule):
            return module_key
    return None


def permission_summary(keys: list[str] | None) -> str:
    if not keys:
        return "无"
    key_set = set(keys)
    default_set = set(STORE_DEFAULT_PERMISSIONS)
    if key_set == default_set:
        return "标准"
    extra = key_set - default_set
    if default_set <= key_set:
        return f"标准+{len(extra)}"
    return f"{len(keys)}项"
