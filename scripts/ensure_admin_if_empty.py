"""
Создаёт пользователя admin (логин/пароль: admin/admin) только если в базе ещё нет ни одного пользователя.
Используется при старте контейнера, чтобы не перезаписывать пароли при монтировании своей БД.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash

from app.config import SYNC_DATABASE_URL, BASE_DIR
from app.database import Base
from app.models import User
from app.models.user import UserRole


def main():
    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
    engine = create_engine(SYNC_DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        if session.scalar(select(func.count()).select_from(User)) > 0:
            return  # уже есть пользователи — ничего не делаем
        username = os.getenv("ADMIN_USER", "admin")
        password = os.getenv("ADMIN_PASSWORD", "admin")
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role=UserRole.admin,
        )
        session.add(user)
        session.commit()
        print(f"Created admin user '{username}' (password: {password}).")


if __name__ == "__main__":
    main()
