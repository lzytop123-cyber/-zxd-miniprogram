"""Inspect meituan_orders raw payloads for price fields."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import MeituanOrder, MeituanOrderStatus, PeriodCard


def main() -> None:
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(MeituanOrder)
            .where(MeituanOrder.status == MeituanOrderStatus.verified)
            .order_by(MeituanOrder.id.desc())
            .limit(20)
        ).all()
        for r in rows:
            raw = r.meituan_raw if isinstance(r.meituan_raw, dict) else {}
            td = raw.get("ticketData") if isinstance(raw.get("ticketData"), dict) else {}
            card = None
            if r.coupon_code:
                card = db.scalar(
                    select(PeriodCard).where(PeriodCard.meituan_receipt == r.coupon_code).limit(1)
                )
            src = card.source.value if card and card.source else "?"
            print("=" * 60)
            print(f"id={r.id} deal_price={r.deal_price} source={src} name={r.deal_name}")
            print(f"raw_keys={list(raw.keys())}")
            print(f"td_keys={list(td.keys())}")
            print(f"td.dealPrice={td.get('dealPrice')} td.amount={td.get('amount')}")
            print(f"has_raw_prepare={'raw_prepare' in raw}")
            res = raw.get("result")
            if isinstance(res, str):
                try:
                    j = json.loads(res)
                    print(f"result_type=json keys={list(j.keys())}")
                    vr = j.get("verify_result") or {}
                    if isinstance(vr, dict):
                        print(f"verify_result_keys={list(vr.keys())}")
                        cert = vr.get("certificate")
                        if isinstance(cert, dict):
                            print(f"cert.amount={cert.get('amount')} sku={cert.get('sku')}")
                    rv = j.get("raw_verify") or {}
                    if isinstance(rv, dict):
                        print(f"raw_verify_keys={list(rv.keys())}")
                except Exception as e:
                    print(f"result_str_len={len(res)} parse_err={e}")
            elif isinstance(res, dict):
                print(f"result_dict_keys={list(res.keys())}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
