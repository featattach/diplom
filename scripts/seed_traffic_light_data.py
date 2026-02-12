"""
Тестовые данные для отчёта «Светофор»: 5 организаций, по 15 единиц каждого типа
(системный блок, неттоп, ноутбук, сервер) с разными датами производства и заполненными полями.
Запуск из корня проекта: python -m scripts.seed_traffic_light_data
"""
import sys
from pathlib import Path
from datetime import datetime, date, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import SYNC_DATABASE_URL, BASE_DIR
from app.database import Base
from app.models import Asset, Company
from app.models.asset import AssetStatus

# 5 организаций
COMPANIES = [
    {"name": "ООО «Альфа-Техно»", "short_info": "Разработка ПО. Офис Москва."},
    {"name": "ООО «Бета-Логистик»", "short_info": "Логистика и склад. Учёт техники по филиалам."},
    {"name": "АО «Гамма-Связь»", "short_info": "Телеком. Серверные и офисы в 3 регионах."},
    {"name": "ГБУ «Центр образования № 1»", "short_info": "Школа. Компьютерные классы, администрация."},
    {"name": "ИП «Дельта-Сервис»", "short_info": "ИТ-обслуживание. Небольшой офис."},
]

# Типы для светофора (по 15 шт на организацию)
TRAFFIC_LIGHT_KINDS = ["desktop", "nettop", "laptop", "server"]
KIND_LABELS = {"desktop": "ПК", "nettop": "Неттоп", "laptop": "Ноутбук", "server": "Сервер"}

# Распределение дат производства для 15 единиц: серый / зелёный / жёлтый / красный
# 3 без даты, 4 зелёных (<3 лет), 4 жёлтых (3–5 лет), 4 красных (>5 лет)
def manufacture_dates_for_fifteen(today: date):
    out = [None] * 3  # нет даты
    # зелёный: 0.5, 1, 1.5, 2 года назад
    for years in [0.5, 1, 1.5, 2]:
        out.append(today - timedelta(days=int(365.25 * years)))
    # жёлтый: 3, 3.5, 4, 4.5 года назад
    for years in [3, 3.5, 4, 4.5]:
        out.append(today - timedelta(days=int(365.25 * years)))
    # красный: 5.5, 6, 7, 8 лет назад
    for years in [5.5, 6, 7, 8]:
        out.append(today - timedelta(days=int(365.25 * years)))
    return out


def make_asset_templates(kind: str, location_prefix: str, serial_prefix: str):
    """Шаблоны полей для одного типа техники (15 вариантов)."""
    if kind == "desktop":
        return [
            {
                "name": f"Системный блок {location_prefix} #{i:02d}",
                "model": ["HP ProDesk 400 G6", "Lenovo ThinkCentre M720", "Dell OptiPlex 3080", "Acer Veriton"][i % 4],
                "location": f"{location_prefix}, каб. {100 + (i % 5)}",
                "cpu": ["Intel Core i5-10500", "Intel Core i3-10100", "AMD Ryzen 5 3600", "Intel Core i7-10700"][i % 4],
                "ram": ["8 ГБ DDR4", "16 ГБ DDR4", "8 ГБ", "32 ГБ DDR4"][i % 4],
                "disk1_type": "SSD",
                "disk1_capacity": ["256 ГБ", "512 ГБ", "256 ГБ", "1 ТБ"][i % 4],
                "motherboard": "Материнская плата OEM",
                "power_supply": "300 Вт",
                "os": ["windows_10", "windows_11", "linux", "windows_10"][i % 4],
                "current_user": ["Иванов И.И.", "Петрова М.С.", "Сидоров А.В.", ""][i % 4],
            }
            for i in range(1, 16)
        ]
    if kind == "nettop":
        return [
            {
                "name": f"Неттоп {location_prefix} #{i:02d}",
                "model": ["Intel NUC 10", "Intel NUC 11", "ASUS PN50", "Lenovo ThinkCentre M90n"][i % 4],
                "location": f"{location_prefix}, ресепшен/каб. {i % 10}",
                "cpu": ["Intel Celeron J4125", "Intel Core i3-1115G4", "AMD Ryzen 3 4300U", "Intel Pentium"][i % 4],
                "ram": ["4 ГБ", "8 ГБ", "8 ГБ DDR4", "4 ГБ"][i % 4],
                "disk1_type": "SSD",
                "disk1_capacity": ["128 ГБ", "256 ГБ", "256 ГБ", "128 ГБ"][i % 4],
                "os": ["windows_10", "linux", "windows_10", "windows_11"][i % 4],
                "current_user": ["Ресепшен", "Вахта", "", "Склад"][i % 4],
            }
            for i in range(1, 16)
        ]
    if kind == "laptop":
        return [
            {
                "name": f"Ноутбук {location_prefix} #{i:02d}",
                "model": ["Dell Latitude 5520", "HP ProBook 450 G8", "Lenovo ThinkPad E14", "Acer TravelMate"][i % 4],
                "location": f"{location_prefix}, каб. {200 + (i % 3)}",
                "cpu": ["Intel Core i7-1185G7", "Intel Core i5-1135G7", "AMD Ryzen 5 5500U", "Intel Core i5-10210U"][i % 4],
                "ram": ["16 ГБ", "8 ГБ", "16 ГБ DDR4", "8 ГБ"][i % 4],
                "disk1_type": "SSD",
                "disk1_capacity": ["512 ГБ", "256 ГБ", "512 ГБ", "256 ГБ"][i % 4],
                "screen_diagonal": "15.6\"",
                "screen_resolution": "1920×1080",
                "os": ["windows_11", "windows_10", "windows_10", "linux"][i % 4],
                "current_user": ["Директор", "Менеджер", "Бухгалтер", "Сотрудник"][i % 4],
            }
            for i in range(1, 16)
        ]
    # server
    return [
        {
            "name": f"Сервер {location_prefix} #{i:02d}",
            "model": ["Dell PowerEdge R340", "HP ProLiant DL380 Gen10", "Lenovo ThinkSystem SR650", "Supermicro"][i % 4],
            "location": f"{location_prefix}, серверная",
            "cpu": ["Intel Xeon E-2224", "Intel Xeon Silver 4210", "Intel Xeon Gold 5218", "AMD EPYC"][i % 4],
            "ram": ["32 ГБ", "64 ГБ DDR4", "128 ГБ", "32 ГБ ECC"][i % 4],
            "disk1_type": "SSD",
            "disk1_capacity": ["480 ГБ", "1 ТБ NVMe", "2×960 ГБ RAID", "512 ГБ"][i % 4],
            "rack_units": [1, 2, 1, 2][i % 4],
            "os": ["linux", "windows_10", "linux", "linux"][i % 4],
            "current_user": "",
        }
        for i in range(1, 16)
    ]


def main():
    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
    engine = create_engine(SYNC_DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    today = date.today()
    manufacture_date_list = manufacture_dates_for_fifteen(today)

    with Session() as session:
        # Проверяем, есть ли уже организации из списка
        existing_first = session.execute(select(Company).where(Company.name == COMPANIES[0]["name"])).scalars().first()
        if existing_first:
            # Организации есть — проверяем, добавлены ли активы (по серийнику ALF-)
            has_assets = session.execute(select(Asset.id).where(Asset.serial_number.like("ALF-%")).limit(1)).scalars().first() is not None
            if has_assets:
                print("Данные для светофора уже добавлены (найдены активы с префиксом ALF-).")
                return
            # Подтягиваем все 5 организаций по имени
            company_rows = []
            for c in COMPANIES:
                comp = session.execute(select(Company).where(Company.name == c["name"])).scalars().first()
                if comp:
                    company_rows.append((comp.id, comp.name))
            if len(company_rows) != 5:
                print("Найдена часть организаций из списка, но не все 5. Добавьте недостающие вручную или удалите и запустите скрипт снова.")
                return
            print("Найдено 5 организаций, добавляем технику...")
        else:
            # Создаём 5 организаций
            company_rows = []
            for c in COMPANIES:
                company = Company(name=c["name"], short_info=c["short_info"])
                session.add(company)
                session.flush()
                company_rows.append((company.id, company.name))
            session.commit()
            print(f"Создано организаций: {len(company_rows)}")

        # Префиксы для серийников и локаций
        prefixes = [
            ("ALF", "Альфа офис"),
            ("BET", "Бета склад"),
            ("GAM", "Гамма ДЦ"),
            ("SCH", "Школа №1"),
            ("DEL", "Дельта офис"),
        ]

        assets_created = 0
        for idx, (company_id, company_name) in enumerate(company_rows):
            serial_prefix = prefixes[idx][0]
            location_prefix = prefixes[idx][1]

            for kind in TRAFFIC_LIGHT_KINDS:
                short = {"desktop": "D", "nettop": "N", "laptop": "L", "server": "S"}[kind]
                templates_list = make_asset_templates(kind, location_prefix, serial_prefix)

                for i, (tmpl, mdate) in enumerate(zip(templates_list, manufacture_date_list)):
                    serial = f"{serial_prefix}-{short}-{i+1:03d}"
                    asset = Asset(
                        name=tmpl["name"],
                        serial_number=serial,
                        equipment_kind=kind,
                        model=tmpl.get("model"),
                        location=tmpl.get("location"),
                        status=AssetStatus.active,
                        description=f"Тестовые данные для отчёта Светофор. {company_name}.",
                        company_id=company_id,
                        last_seen_at=datetime.now(timezone.utc),
                        cpu=tmpl.get("cpu"),
                        ram=tmpl.get("ram"),
                        disk1_type=tmpl.get("disk1_type"),
                        disk1_capacity=tmpl.get("disk1_capacity"),
                        motherboard=tmpl.get("motherboard"),
                        power_supply=tmpl.get("power_supply"),
                        screen_diagonal=tmpl.get("screen_diagonal"),
                        screen_resolution=tmpl.get("screen_resolution"),
                        rack_units=tmpl.get("rack_units"),
                        os=tmpl.get("os"),
                        current_user=tmpl.get("current_user") or None,
                        manufacture_date=mdate,
                    )
                    session.add(asset)
                    assets_created += 1

        session.commit()
        print(f"Создано единиц техники: {assets_created} (15 шт каждого из 4 типов в 5 организациях)")

    print("Готово. Откройте отчёт «Светофор» — будут видны все цвета (красный, жёлтый, зелёный, серый).")


if __name__ == "__main__":
    main()
