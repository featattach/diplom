from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class AssetStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    maintenance = "maintenance"
    retired = "retired"


class AssetEventType(str, enum.Enum):
    created = "created"
    updated = "updated"
    moved = "moved"
    assigned = "assigned"
    returned = "returned"
    maintenance = "maintenance"
    retired = "retired"
    other = "other"


class EquipmentKind(str, enum.Enum):
    """Тип техники: от него зависят отображаемые поля."""
    desktop = "desktop"       # системный блок (без диагонали)
    nettop = "nettop"         # неттоп
    laptop = "laptop"         # ноутбук
    monitor = "monitor"       # монитор
    mfu = "mfu"               # МФУ
    printer = "printer"       # принтер
    scanner = "scanner"       # сканер
    switch = "switch"         # коммутатор
    server = "server"         # сервер (есть поле U — юниты)
    sip_phone = "sip_phone"   # SIP-телефон


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=True)
    asset_type: Mapped[str] = mapped_column(String(128), nullable=True)
    equipment_kind: Mapped[str] = mapped_column(String(32), nullable=True)
    model: Mapped[str] = mapped_column(String(256), nullable=True)
    location: Mapped[str] = mapped_column(String(256), nullable=True)
    status: Mapped[AssetStatus] = mapped_column(default=AssetStatus.active, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    # Технические поля
    cpu: Mapped[str] = mapped_column(String(128), nullable=True)
    ram: Mapped[str] = mapped_column(String(64), nullable=True)
    disk1_type: Mapped[str] = mapped_column(String(32), nullable=True)
    disk1_capacity: Mapped[str] = mapped_column(String(64), nullable=True)
    network_card: Mapped[str] = mapped_column(String(128), nullable=True)
    motherboard: Mapped[str] = mapped_column(String(128), nullable=True)
    screen_diagonal: Mapped[str] = mapped_column(String(32), nullable=True)  # ноутбук, монитор
    screen_resolution: Mapped[str] = mapped_column(String(64), nullable=True)
    power_supply: Mapped[str] = mapped_column(String(128), nullable=True)
    monitor_diagonal: Mapped[str] = mapped_column(String(32), nullable=True)
    rack_units: Mapped[int] = mapped_column(Integer, nullable=True)  # сервер: высота в юнитах (U)
    extra_components: Mapped[str] = mapped_column(Text, nullable=True)  # JSON: доп. устройства
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    # ОС (для ПК, ноутбуков, серверов)
    os: Mapped[str] = mapped_column(String(64), nullable=True)
    # Сетевые интерфейсы: JSON [{ "label": "Сетевая карта 1", "type": "network"|"oob", "ip": "..." }]
    network_interfaces: Mapped[str] = mapped_column(Text, nullable=True)
    # Кто сейчас использует (вводимое поле)
    current_user: Mapped[str] = mapped_column(String(256), nullable=True)

    events: Mapped[list["AssetEvent"]] = relationship(
        "AssetEvent",
        back_populates="asset",
    )
    inventory_items: Mapped[list["InventoryItem"]] = relationship(
        "InventoryItem",
        back_populates="asset",
    )
    company: Mapped["Company"] = relationship("Company", back_populates="assets", lazy="selectin")


class AssetEvent(Base):
    __tablename__ = "asset_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[AssetEventType] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    # JSON: список {"field_label": "Расположение", "old": "...", "new": "..."} для отображения «было → стало»
    changes_json: Mapped[str] = mapped_column(Text, nullable=True)

    asset: Mapped["Asset"] = relationship("Asset", back_populates="events")
