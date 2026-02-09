"""
Заполнение системы примерными данными: организации, кампании инвентаризации, техника.
Запуск из корня проекта: python -m scripts.seed_sample_data
"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import SYNC_DATABASE_URL, BASE_DIR
from app.database import Base
from app.models import User, Asset, AssetEvent, InventoryCampaign, InventoryItem, Company
from app.models.asset import AssetStatus

# Организации с кратким описанием
COMPANIES = [
    {"name": "ООО «ИТ-Сервис»", "short_info": "IT-аутсорсинг, обслуживание офисной техники. Контакт: +7 (495) 123-45-67."},
    {"name": "ООО «Склад-Логистик»", "short_info": "Складской комплекс. Учёт техники в офисах и на складах."},
    {"name": "АО «РегионТелеком»", "short_info": "Телеком-оператор. Серверные, офис, удалённые точки."},
    {"name": "ГБУ «Школа № 100»", "short_info": "Образовательное учреждение. Компьютерные классы, администрация, серверная."},
]

# Кампании: для каждой организации — завершённая за 2025 и текущая за 2026
def make_campaigns(company_id: int, company_name: str):
    return [
        {
            "name": f"Инвентаризация {company_name} — 2025",
            "description": "Годовая инвентаризация за 2025 год.",
            "started_at": datetime(2025, 11, 1, 9, 0),
            "finished_at": datetime(2025, 11, 15, 18, 0),
            "company_id": company_id,
        },
        {
            "name": f"Инвентаризация {company_name} — 2026",
            "description": "Плановая инвентаризация на 2026 год.",
            "started_at": datetime(2026, 1, 10, 9, 0),
            "finished_at": None,
            "company_id": company_id,
        },
    ]

# Шаблоны техники по категориям (название, тип, модель, локация, доп. поля)
def make_assets(company_id: int, location_prefix: str, serial_prefix: str):
    return [
        # Системные блоки
        {"name": "ПК бухгалтерия", "equipment_kind": "desktop", "model": "HP ProDesk 400 G6", "location": f"{location_prefix}, каб. 101", "serial_number": f"{serial_prefix}-PC-01", "cpu": "Intel Core i5-10500", "ram": "8 ГБ DDR4", "disk1_type": "SSD", "disk1_capacity": "256 ГБ"},
        {"name": "ПК менеджер", "equipment_kind": "desktop", "model": "Lenovo ThinkCentre M720", "location": f"{location_prefix}, каб. 102", "serial_number": f"{serial_prefix}-PC-02", "cpu": "Intel Core i3-9100", "ram": "8 ГБ", "disk1_type": "SSD", "disk1_capacity": "256 ГБ"},
        # Неттопы
        {"name": "Неттоп ресепшен", "equipment_kind": "nettop", "model": "Intel NUC 10", "location": f"{location_prefix}, ресепшен", "serial_number": f"{serial_prefix}-NET-01", "cpu": "Intel Celeron", "ram": "4 ГБ", "disk1_type": "SSD", "disk1_capacity": "128 ГБ"},
        # Ноутбуки
        {"name": "Ноутбук директора", "equipment_kind": "laptop", "model": "Dell Latitude 5520", "location": f"{location_prefix}, каб. 201", "serial_number": f"{serial_prefix}-NB-01", "cpu": "Intel Core i7-1185G7", "ram": "16 ГБ", "screen_diagonal": "15.6\"", "disk1_type": "SSD", "disk1_capacity": "512 ГБ"},
        {"name": "Ноутбук выездной", "equipment_kind": "laptop", "model": "HP ProBook 450 G8", "location": f"{location_prefix}, склад", "serial_number": f"{serial_prefix}-NB-02", "cpu": "Intel Core i5-1135G7", "ram": "8 ГБ", "screen_diagonal": "15.6\"", "disk1_type": "SSD", "disk1_capacity": "256 ГБ"},
        # Мониторы
        {"name": "Монитор 101-1", "equipment_kind": "monitor", "model": "Dell P2222H 21.5\"", "location": f"{location_prefix}, каб. 101", "serial_number": f"{serial_prefix}-MON-01", "screen_diagonal": "21.5\"", "screen_resolution": "1920×1080"},
        {"name": "Монитор 102-1", "equipment_kind": "monitor", "model": "LG 24MP88HV", "location": f"{location_prefix}, каб. 102", "serial_number": f"{serial_prefix}-MON-02", "screen_diagonal": "24\"", "screen_resolution": "1920×1080"},
        # МФУ
        {"name": "МФУ общий", "equipment_kind": "mfu", "model": "Canon i-SENSYS MF445dw", "location": f"{location_prefix}, коридор", "serial_number": f"{serial_prefix}-MFU-01"},
        # Принтер
        {"name": "Принтер печать форм", "equipment_kind": "printer", "model": "HP LaserJet Pro M404dn", "location": f"{location_prefix}, каб. 101", "serial_number": f"{serial_prefix}-PRN-01"},
        # Сканер
        {"name": "Сканер документов", "equipment_kind": "scanner", "model": "Epson WorkForce ES-50", "location": f"{location_prefix}, каб. 102", "serial_number": f"{serial_prefix}-SCN-01"},
        # Коммутатор
        {"name": "Коммутатор этаж 1", "equipment_kind": "switch", "model": "Cisco SG350-28", "location": f"{location_prefix}, серверная", "serial_number": f"{serial_prefix}-SW-01"},
        # Сервер
        {"name": "Сервер 1С", "equipment_kind": "server", "model": "Dell PowerEdge R340", "location": f"{location_prefix}, серверная", "serial_number": f"{serial_prefix}-SRV-01", "cpu": "Intel Xeon E-2224", "ram": "32 ГБ", "rack_units": 1, "disk1_type": "SSD", "disk1_capacity": "480 ГБ"},
    ]


def main():
    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
    engine = create_engine(SYNC_DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        # Проверяем, есть ли уже данные
        has_companies = session.execute(select(Company).limit(1)).scalars().first() is not None
        if has_companies:
            print("В базе уже есть организации. Скрипт добавляет данные только в пустую систему.")
            print("Для повторного заполнения удалите или очистите таблицы companies, inventory_campaigns, assets (и связанные).")
            return

        # 1. Организации
        company_rows = []
        for c in COMPANIES:
            company = Company(name=c["name"], short_info=c["short_info"])
            session.add(company)
            session.flush()
            company_rows.append((company.id, company.name))
        session.commit()
        print(f"Создано организаций: {len(company_rows)}")

        # 2. Кампании по каждой организации
        campaigns_created = 0
        for company_id, company_name in company_rows:
            for camp_data in make_campaigns(company_id, company_name):
                camp = InventoryCampaign(
                    name=camp_data["name"],
                    description=camp_data["description"],
                    started_at=camp_data["started_at"],
                    finished_at=camp_data["finished_at"],
                    company_id=camp_data["company_id"],
                )
                session.add(camp)
                campaigns_created += 1
        session.commit()
        print(f"Создано кампаний инвентаризации: {campaigns_created}")

        # 3. Техника по организациям (разные префиксы серийников и локаций)
        prefixes = [
            ("ИТС", "Офис ИТ-Сервис"),
            ("СКЛ", "Склад-Логистик"),
            ("РТК", "РегионТелеком"),
            ("ШК100", "Школа 100"),
        ]
        assets_created = 0
        for idx, (company_id, _) in enumerate(company_rows):
            serial_prefix = prefixes[idx][0]
            location_prefix = prefixes[idx][1]
            for a in make_assets(company_id, location_prefix, serial_prefix):
                asset = Asset(
                    name=a["name"],
                    equipment_kind=a.get("equipment_kind"),
                    model=a.get("model"),
                    location=a.get("location"),
                    serial_number=a.get("serial_number"),
                    status=AssetStatus.active,
                    company_id=company_id,
                    last_seen_at=datetime.utcnow(),  # чтобы на дашборде отображались как «активные» (по последней активности)
                    cpu=a.get("cpu"),
                    ram=a.get("ram"),
                    disk1_type=a.get("disk1_type"),
                    disk1_capacity=a.get("disk1_capacity"),
                    network_card=a.get("network_card"),
                    screen_diagonal=a.get("screen_diagonal"),
                    screen_resolution=a.get("screen_resolution"),
                    rack_units=a.get("rack_units"),
                )
                session.add(asset)
                assets_created += 1
        session.commit()
        print(f"Создано единиц техники: {assets_created}")

    # Чтобы после сида «alembic upgrade head» не пытался заново создавать таблицы
    try:
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config(str(BASE_DIR / "alembic.ini"))
        command.stamp(alembic_cfg, "head")
    except Exception:
        pass  # если alembic недоступен или нет alembic.ini — не ломаем сидер

    print("Готово. Можно открыть раздел «Инвентаризация» и карточки организаций/оборудования.")


if __name__ == "__main__":
    main()
