import os
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.db import Base


# В модульных тестах схема отключается (SQLite).
SCHEMA = None if os.getenv("SKIP_DB_INIT") == "1" else settings.schema_name


def _table_args() -> dict:
    return {"schema": SCHEMA} if SCHEMA else {}


def _fk(table: str) -> str:
    return f"{SCHEMA}.{table}.id" if SCHEMA else f"{table}.id"


class User(Base):
    __tablename__ = "users"
    __table_args__ = _table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Reader(Base):
    __tablename__ = "readers"
    __table_args__ = _table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    ticket_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    registered_at: Mapped[date] = mapped_column(Date, nullable=False)

    loans: Mapped[list["Loan"]] = relationship(back_populates="reader")


class Book(Base):
    __tablename__ = "books"
    __table_args__ = _table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    author: Mapped[str] = mapped_column(String(200), nullable=False)
    isbn: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    copies: Mapped[list["Copy"]] = relationship(back_populates="book")


class Copy(Base):
    __tablename__ = "copies"
    __table_args__ = _table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey(_fk("books")), nullable=False)
    inventory_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="available")

    book: Mapped["Book"] = relationship(back_populates="copies")
    loans: Mapped[list["Loan"]] = relationship(back_populates="copy")


class Loan(Base):
    __tablename__ = "loans"
    __table_args__ = _table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reader_id: Mapped[int] = mapped_column(ForeignKey(_fk("readers")), nullable=False)
    copy_id: Mapped[int] = mapped_column(ForeignKey(_fk("copies")), nullable=False)
    issued_at: Mapped[date] = mapped_column(Date, nullable=False)
    due_at: Mapped[date] = mapped_column(Date, nullable=False)
    returned_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    overdue_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fine_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    reader: Mapped["Reader"] = relationship(back_populates="loans")
    copy: Mapped["Copy"] = relationship(back_populates="loans")
