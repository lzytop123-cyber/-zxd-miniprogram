"""将误发为 monthly 的上班族/夜读月卡批量纠正为 night_monthly。"""

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import CardType, PeriodCard
from app.services.card_service import ensure_office_night_card_type, is_office_night_monthly_card


def main() -> None:
    db = SessionLocal()
    try:
        cards = db.scalars(
            select(PeriodCard).where(
                PeriodCard.status == 1,
                PeriodCard.card_type == CardType.monthly,
            )
        ).all()
        fixed = 0
        for card in cards:
            if not is_office_night_monthly_card(card):
                continue
            ensure_office_night_card_type(db, card)
            fixed += 1
            print(f"fixed card #{card.id} {card.card_name!r} -> night_monthly")
        db.commit()
        print(f"done, fixed {fixed} card(s)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
