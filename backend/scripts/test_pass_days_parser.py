"""团购名称 → 连续天数解析测试。"""
from app.services.pass_days_parser import parse_pass_days_from_name
from app.services.deal_mapping_service import guess_reward_from_name
from app.models import RewardType


def test_parse_nine_month_card():
    assert parse_pass_days_from_name("9月卡") == 270
    assert parse_pass_days_from_name("通坐9个月卡") == 270


def test_parse_bimonthly():
    assert parse_pass_days_from_name("「暑期」双月卡") == 60


def test_parse_days():
    assert parse_pass_days_from_name("90天畅学卡") == 90


def test_guess_nine_month_mapping():
    reward_type, value = guess_reward_from_name("知行岛9月卡")
    assert reward_type == RewardType.month_pass
    assert value == 270


if __name__ == "__main__":
    test_parse_nine_month_card()
    test_parse_bimonthly()
    test_parse_days()
    test_guess_nine_month_mapping()
    print("ok")
