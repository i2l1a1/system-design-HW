from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    scooter_id: Mapped[str] = mapped_column(Text, nullable=False)
    zone_id: Mapped[str] = mapped_column(Text, nullable=False)
    price_per_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    price_unlock: Mapped[int] = mapped_column(Integer, nullable=False)
    deposit: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    offer_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("offers.id"),
        nullable=False,
        unique=True,
    )
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    scooter_id: Mapped[str] = mapped_column(Text, nullable=False)
    price_per_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    price_unlock: Mapped[int] = mapped_column(Integer, nullable=False)
    deposit: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finish_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Debt(Base):
    __tablename__ = "debts"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    order_id: Mapped[str] = mapped_column(Text, ForeignKey("orders.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    repaid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserReliability(Base):
    __tablename__ = "user_reliability"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column("key", Text, primary_key=True)
    order_id: Mapped[str] = mapped_column(Text, ForeignKey("orders.id"), nullable=False)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PaymentOperation(Base):
    __tablename__ = "payment_operations"

    payment_key: Mapped[str] = mapped_column(Text, primary_key=True)
    order_id: Mapped[str] = mapped_column(Text, ForeignKey("orders.id"), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
