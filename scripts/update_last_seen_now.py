"""
Проставляет «последняя активность» (last_seen_at) = сейчас у всех активов со статусом «Активно»
и пустым last_seen_at. После этого на дашборде они будут учитываться как «активные».
Запуск: python -m scripts.update_last_seen_now
"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, update, and_
from sqlalchemy.orm import sessionmaker

from app.config import SYNC_DATABASE_URL, BASE_DIR
from app.database import Base
from app.models import Asset
from app.models.asset import AssetStatus


def main():
    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
    engine = create_engine(SYNC_DATABASE_URL, echo=False)
    Session = sessionmaker(bind=engine)
    now = datetime.utcnow()
    with Session() as session:
        result = session.execute(
            update(Asset).where(
                and_(Asset.status == AssetStatus.active, Asset.last_seen_at.is_(None))
            ).values(last_seen_at=now)
        )
        session.commit()
        n = result.rowcount
    print(f"Обновлено активов (проставлена последняя активность): {n}.")


if __name__ == "__main__":
    main()
