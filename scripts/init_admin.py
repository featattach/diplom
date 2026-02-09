"""
Create admin user. Run from project root:
  python -m scripts.init_admin
Or with custom username/password:
  ADMIN_USER=admin ADMIN_PASSWORD=secret python -m scripts.init_admin
"""
import os
import sys
from pathlib import Path

# Project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash

from app.config import SYNC_DATABASE_URL, BASE_DIR
from app.database import Base
from app.models import User, Asset, AssetEvent, InventoryCampaign, InventoryItem  # noqa: F401
from app.models.user import UserRole


def main():
    username = os.getenv("ADMIN_USER", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin")
    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
    engine = create_engine(SYNC_DATABASE_URL, echo=False)
    # Ensure tables exist (e.g. after alembic upgrade head)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        existing = session.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if existing:
            existing.password_hash = generate_password_hash(password)
            existing.role = UserRole.admin
            session.commit()
            print(f"Updated user '{username}' with admin role and new password.")
        else:
            user = User(
                username=username,
                password_hash=generate_password_hash(password),
                role=UserRole.admin,
            )
            session.add(user)
            session.commit()
            print(f"Created admin user '{username}'.")
    print("Done.")


if __name__ == "__main__":
    main()
