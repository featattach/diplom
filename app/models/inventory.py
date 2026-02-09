from __future__ import annotations

from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InventoryCampaign(Base):
    __tablename__ = "inventory_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
    )

    items: Mapped[list["InventoryItem"]] = relationship(
        "InventoryItem",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )
    company: Mapped["Company"] = relationship("Company", back_populates="campaigns")


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    expected_location: Mapped[str] = mapped_column(String(256), nullable=True)
    found: Mapped[bool] = mapped_column(Boolean, default=False)
    found_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    campaign: Mapped["InventoryCampaign"] = relationship("InventoryCampaign", back_populates="items")
    asset: Mapped["Asset"] = relationship("Asset", back_populates="inventory_items")
