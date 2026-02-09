from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    short_info: Mapped[str] = mapped_column(Text, nullable=True)

    assets: Mapped[list["Asset"]] = relationship(
        "Asset",
        back_populates="company",
    )
    campaigns: Mapped[list["InventoryCampaign"]] = relationship(
        "InventoryCampaign",
        back_populates="company",
    )
