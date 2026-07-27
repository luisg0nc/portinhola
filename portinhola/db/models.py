from datetime import date

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from portinhola.db.base import Base


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column()


class SupplyPoint(Base):
    __tablename__ = "supply_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    utility: Mapped[str] = mapped_column()
    identifier: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(default="")


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    supply_point_id: Mapped[int] = mapped_column(ForeignKey("supply_points.id"))
    supplier_name: Mapped[str] = mapped_column()
    supplier_nif: Mapped[str] = mapped_column()
    tariff_name: Mapped[str] = mapped_column(default="")
    power_kva: Mapped[float | None] = mapped_column(default=None)
    cycle: Mapped[str | None] = mapped_column(default=None)
    gas_tier: Mapped[int | None] = mapped_column(default=None)
    start_date: Mapped[date] = mapped_column()
    end_date: Mapped[date | None] = mapped_column(default=None)

    supply_point: Mapped[SupplyPoint] = relationship()


class Bill(Base):
    __tablename__ = "bills"

    id: Mapped[int] = mapped_column(primary_key=True)
    issuer_nif: Mapped[str] = mapped_column()
    customer_nif: Mapped[str | None] = mapped_column(default=None)
    doc_type: Mapped[str] = mapped_column(default="FT")
    doc_number: Mapped[str] = mapped_column()
    atcud: Mapped[str | None] = mapped_column(unique=True, default=None)
    issue_date: Mapped[date] = mapped_column()
    period_start: Mapped[date | None] = mapped_column(default=None)
    period_end: Mapped[date | None] = mapped_column(default=None)
    total_cents: Mapped[int] = mapped_column()
    vat_json: Mapped[str] = mapped_column(default="{}")
    pdf_path: Mapped[str | None] = mapped_column(default=None)
    parse_status: Mapped[str] = mapped_column()
    extractor: Mapped[str | None] = mapped_column(default=None)
    qr_raw: Mapped[str | None] = mapped_column(default=None)

    lines: Mapped[list["BillLine"]] = relationship(
        back_populates="bill", cascade="all, delete-orphan"
    )


class BillLine(Base):
    __tablename__ = "bill_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    bill_id: Mapped[int] = mapped_column(ForeignKey("bills.id"))
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id"), default=None)
    description: Mapped[str] = mapped_column()
    category: Mapped[str] = mapped_column()
    period_start: Mapped[date | None] = mapped_column(default=None)
    period_end: Mapped[date | None] = mapped_column(default=None)
    quantity: Mapped[float | None] = mapped_column(default=None)
    unit: Mapped[str | None] = mapped_column(default=None)
    unit_price: Mapped[float | None] = mapped_column(default=None)
    amount_cents: Mapped[int] = mapped_column()
    vat_rate: Mapped[int | None] = mapped_column(default=None)

    bill: Mapped[Bill] = relationship(back_populates="lines")
