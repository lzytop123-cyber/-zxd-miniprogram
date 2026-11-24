"""云飞 prepare 归一化冒烟测试（不打真实接口）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.yunfei import YunfeiService  # noqa: E402


def main() -> int:
    raw = {
        "dealId": 702566611,
        "dealTitle": "全日卡体验",
        "payAmount": 1990,
        "receiptCode": "4853638755",
        "receiptEndDate": 1730908799000,
        "verifyCount": 1,
        "result": [
            {
                "dealId": 702566611,
                "dealPrice": 19.9,
                "dealTitle": "全日卡体验",
                "receiptCode": "4853638755",
            }
        ],
    }
    prepared = YunfeiService._normalize_prepare("4853638755", raw, "poi-ligongda")
    assert prepared["ticketName"] == "全日卡体验"
    assert prepared["ticketData"]["dealId"] == "702566611"
    assert prepared["ticketData"]["dealPrice"] == 19.9
    assert prepared["payAmount"] == 19.9
    assert prepared["_yunfei_op_poi_id"] == "poi-ligongda"
    assert prepared["_yunfei_verify_count"] == 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
