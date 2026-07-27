from datetime import date, datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
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
    reading_day_start: Mapped[int | None] = mapped_column(default=None)
    reading_day_end: Mapped[int | None] = mapped_column(default=None)
    submit_url: Mapped[str] = mapped_column(default="")
    submit_phone: Mapped[str] = mapped_column(default="")
    submit_reference: Mapped[str] = mapped_column(default="")

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


class Reading(Base):
    __tablename__ = "readings"

    id: Mapped[int] = mapped_column(primary_key=True)
    supply_point_id: Mapped[int] = mapped_column(ForeignKey("supply_points.id"))
    register: Mapped[str] = mapped_column()
    value: Mapped[float] = mapped_column()
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submission_status: Mapped[str] = mapped_column(default="not_submitted")
    note: Mapped[str] = mapped_column(default="")


class IntervalConsumption(Base):
    __tablename__ = "interval_consumption"
    __table_args__ = (UniqueConstraint("supply_point_id", "ts"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    supply_point_id: Mapped[int] = mapped_column(ForeignKey("supply_points.id"))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    kwh: Mapped[float] = mapped_column()
    source: Mapped[str] = mapped_column()
    quality: Mapped[str] = mapped_column(default="real")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column()
    status: Mapped[str] = mapped_column()
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    log: Mapped[str] = mapped_column(default="")
    error: Mapped[str | None] = mapped_column(default=None)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column()
    message: Mapped[str] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    read: Mapped[bool] = mapped_column(default=False)
    dedup_key: Mapped[str | None] = mapped_column(unique=True, default=None)


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
