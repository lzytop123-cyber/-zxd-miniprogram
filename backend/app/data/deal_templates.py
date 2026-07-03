"""团购映射标准模板（来自 seed，供后台一键导入）。"""

from app.models import RewardType

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
