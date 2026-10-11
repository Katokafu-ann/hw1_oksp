#!/usr/bin/env python3
"""Воспроизводимое наполнение БД. Повторный запуск с теми же параметрами даёт тот же результат."""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from faker import Faker
from sqlalchemy import text

from app.auth import hash_password
from app.business import calculate_fine, calculate_overdue, due_date_from_issue
from app.config import settings
from app.db import SessionLocal, engine, init_schema
from app.models import Book, Copy, Loan, Reader, User


VOLUMES = {
    "small": {"readers": 50, "books": 100, "copies": 200, "loans": 300},
    "work": {"readers": 3000, "books": 10000, "copies": 30000, "loans": 80000},
}


def reset_schema() -> None:
    with engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {settings.schema_name} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {settings.schema_name}"))
    init_schema()


def seed(volume: str) -> dict[str, int]:
    if volume not in VOLUMES:
        raise SystemExit(f"unknown volume: {volume}")

    cfg = VOLUMES[volume]
    fake = Faker("ru_RU")
    Faker.seed(42)
    random.seed(42)

    reset_schema()
    db = SessionLocal()
    try:
        db.add(User(username="demo", password_hash=hash_password("demo"), is_active=True))
        db.flush()

        readers: list[Reader] = []
        for i in range(cfg["readers"]):
            readers.append(
                Reader(
                    full_name=fake.name(),
                    ticket_number=f"T-{volume}-{i + 1:06d}",
                    email=f"reader{i + 1}@anna_akulova.local",
                    registered_at=date(2020, 1, 1) + timedelta(days=i % 1500),
                )
            )
        db.add_all(readers)
        db.flush()

        books: list[Book] = []
        for i in range(cfg["books"]):
            books.append(
                Book(
                    title=f"{fake.catch_phrase()} {i + 1}",
                    author=fake.name(),
                    isbn=f"978-{volume[:1]}-{i + 1:08d}",
                    year=1980 + (i % 45),
                    description=fake.text(max_nb_chars=120),
                )
            )
        db.add_all(books)
        db.flush()

        copies: list[Copy] = []
        for i in range(cfg["copies"]):
            book = books[i % len(books)]
            copies.append(
                Copy(
                    book_id=book.id,
                    inventory_number=f"INV-{volume}-{i + 1:07d}",
                    status="available",
                )
            )
        db.add_all(copies)
        db.flush()

        # Состояние экземпляров обновляем по открытым выдачам
        open_by_copy: dict[int, Loan] = {}
        loans: list[Loan] = []
        base_day = date(2024, 1, 1)

        for i in range(cfg["loans"]):
            reader = readers[i % len(readers)]
            copy = copies[i % len(copies)]
            issued_at = base_day + timedelta(days=(i * 3) % 700)
            due_at = due_date_from_issue(issued_at)

            # ~35% открытых, остальные возвращены; часть просрочена
            is_open = (i % 100) < 35
            returned_at = None
            overdue_days = 0
            fine_amount = 0

            if is_open:
                # не допускаем две открытые выдачи одного экземпляра
                if copy.id in open_by_copy or copy.status != "available":
                    is_open = False

            if is_open:
                copy.status = "on_loan"
                overdue_days = 0
                fine_amount = 0
            else:
                delay = (i % 40) - 10  # от −10 до +29 дней относительно срока
                returned_at = due_at + timedelta(days=delay)
                overdue_days = calculate_overdue(due_at, returned_at)
                fine_amount = calculate_fine(overdue_days)

            loan = Loan(
                reader_id=reader.id,
                copy_id=copy.id,
                issued_at=issued_at,
                due_at=due_at,
                returned_at=returned_at,
                overdue_days=overdue_days,
                fine_amount=fine_amount,
            )
            loans.append(loan)
            if is_open:
                open_by_copy[copy.id] = loan

        db.add_all(loans)
        db.commit()

        counts = {
            "users": db.query(User).count(),
            "readers": db.query(Reader).count(),
            "books": db.query(Book).count(),
            "copies": db.query(Copy).count(),
            "loans": db.query(Loan).count(),
        }
        return counts
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Наполнение БД anna_akulova")
    parser.add_argument("--volume", choices=["small", "work"], required=True)
    args = parser.parse_args()
    counts = seed(args.volume)
    print(f"volume={args.volume} schema={settings.schema_name}")
    for table, n in counts.items():
        print(f"{table}: {n}")


if __name__ == "__main__":
    main()
