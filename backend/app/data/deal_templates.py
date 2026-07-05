"""团购映射标准模板（来自 seed，供后台一键导入）。

效期规则（兑换日 = T）见 DEAL_VALIDITY_REFERENCE。
发卡逻辑：app/services/card_service.py → validity_days_for_reward / issue_period_card
"""

from app.models import RewardType

# ---------------------------------------------------------------------------
# 效期对照（业务确认 2026-07）
#
# | 产品              | 卡面效期   | reward_value | 预约方式              |
# |-------------------|-----------|--------------|----------------------|
# | 4 小时卡          | 90 天     | 小时数 4     | 按小时               |
# | 50 小时卡         | 180 天    | 小时数 50    | 按小时·可多次        |
# | 日卡              | 90 天     | 1            | 天卡·单日            |
# | 三天卡            | 15 天     | 3            | 须连续 3 天          |
# | 周卡              | 90 天     | 7            | 效期内须连续 7 天    |
# | 通坐月卡          | 180 天    | 30           | 效期内须连续 30 天   |
# | 上班族/夜读月卡   | 90 天     | 30           | 效期内须连续 30 天   |
# | 季卡              | 180 天    | 90(未用于效期)| 季卡·90 天          |
# | 10 次卡           | 90 天     | 10           | 次卡·按天扣次        |
# | 30 次卡           | 360 天    | 30           | 次卡·按天扣次        |
# ---------------------------------------------------------------------------

DEAL_VALIDITY_REFERENCE = {
    RewardType.hours: {
        4: 90,
        50: 180,
        "_default": 90,
    },
    RewardType.session: {
        10: 90,
        30: 360,
        "_default": 90,
    },
    RewardType.day_pass: {
        1: 90,
        3: 15,
    },
    RewardType.week_pass: 90,
    RewardType.month_pass: 180,
    RewardType.quarter_pass: 180,
    RewardType.night_monthly: 90,
}

# (deal_id, deal_name, reward_type, reward_value, night_start, night_end)
DEAL_MAPPING_TEMPLATES: tuple[tuple[str, str, RewardType, int, None, None], ...] = (
    ("1457226281", "团购测试四小时", RewardType.hours, 4, None, None),
    ("1538184020", "团购测试四小时", RewardType.hours, 4, None, None),
    ("1380905696", "「全区域通用 固定座位」季卡", RewardType.quarter_pass, 90, None, None),
    ("1372550283", "「全区域通用 任意30次」30次卡", RewardType.session, 30, None, None),
    ("1378191332", "「全区域通用 可自选」四小时卡", RewardType.hours, 4, None, None),
    ("1358350526", "「全区域通用」十次卡", RewardType.session, 10, None, None),
    ("1345243007", "「可分次·十次通用库」50小时", RewardType.hours, 50, None, None),
    ("1344290952", "「上班族」月卡", RewardType.night_monthly, 30, None, None),
    ("1344305321", "「新客专享·全区域通用」月卡", RewardType.month_pass, 30, None, None),
    ("1344307152", "「全区域通用 固定座位」月卡", RewardType.month_pass, 30, None, None),
    ("1344310042", "「全区域通用」周卡", RewardType.week_pass, 7, None, None),
    ("1344305196", "「全区域通坐 可复购」日卡", RewardType.day_pass, 1, None, None),
    ("1344196515", "「新客专享 全区域通坐」三天卡", RewardType.day_pass, 3, None, None),
    ("1344167767", "「新客专享 全区域通坐」日卡", RewardType.day_pass, 1, None, None),
    ("1392559935", "「新客专享·全区域通坐」日卡", RewardType.day_pass, 1, None, None),
    ("1344166440", "「新客专享 全区域通坐」四小时", RewardType.hours, 4, None, None),
)

DEAL_TEMPLATE_BY_ID = {row[0]: row for row in DEAL_MAPPING_TEMPLATES}
