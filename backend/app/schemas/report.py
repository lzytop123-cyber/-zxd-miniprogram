from datetime import date, datetime, timedelta
from decimal import Decimal

from pydantic import BaseModel, Field


class ReportSummary(BaseModel):
    total_sessions: int
    total_minutes: int
    total_hours: int
    total_minutes_remainder: int
    daily_avg_minutes: int
    title: str
    rank: int | None = None
    beat_percent: float = 0


class DailyStatItem(BaseModel):
    stat_date: date
    total_minutes: int
    session_count: int


class LeaderboardItem(BaseModel):
    rank: int
    nickname: str
    title: str | None
    total_minutes: int
    session_count: int
    is_self: bool = False


class RechargeRequest(BaseModel):
    amount: Decimal = Field(gt=0, le=10000)


class WalletInfo(BaseModel):
    balance: Decimal
    logs: list[dict]
