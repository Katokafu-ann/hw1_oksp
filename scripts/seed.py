#!/usr/bin/env python3

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from faker import Faker
from sqlalchemy import text

from app.auth import hash_password
from app.business import calculate_fine, calculate_overdue, due_date_from_issue
from app.config import settings
from app.db import engine, init_schema
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


def chunks(items: list, size: int = 5000):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def seed(volume: str) -> dict[str, int]:
    if volume not in VOLUMES:
        raise SystemExit(f"unknown volume: {volume}")

    cfg = VOLUMES[volume]
    fake = Faker("ru_RU")
    Faker.seed(42)
    random.seed(42)

    reset_schema()

    readers = [
        {
            "id": i + 1,
            "full_name": fake.name(),
            "ticket_number": f"T-{volume}-{i + 1:06d}",
            "email": f"reader{i + 1}@anna_akulova.local",
            "registered_at": date(2020, 1, 1) + timedelta(days=i % 1500),
        }
        for i in range(cfg["readers"])
    ]
    books = [
        {
            "id": i + 1,
            "title": f"{fake.catch_phrase()} {i + 1}",
            "author": fake.name(),
            "isbn": f"978-{volume[:1]}-{i + 1:08d}",
            "year": 1980 + (i % 45),
            "description": fake.text(max_nb_chars=120),
        }
        for i in range(cfg["books"])
    ]

    copy_status = ["available"] * cfg["copies"]
    copies = [
        {
            "id": i + 1,
            "book_id": (i % cfg["books"]) + 1,
            "inventory_number": f"INV-{volume}-{i + 1:07d}",
            "status": "available",
        }
        for i in range(cfg["copies"])
    ]

    open_copies: set[int] = set()
    base_day = date(2024, 1, 1)
    now = datetime.utcnow()
    loans = []
    for i in range(cfg["loans"]):
        reader_id = (i % cfg["readers"]) + 1
        copy_id = (i % cfg["copies"]) + 1
        issued_at = base_day + timedelta(days=(i * 3) % 700)
        due_at = due_date_from_issue(issued_at)
        is_open = (i % 100) < 35
        if is_open and (copy_id in open_copies or copy_status[copy_id - 1] != "available"):
            is_open = False

        if is_open:
            copy_status[copy_id - 1] = "on_loan"
            open_copies.add(copy_id)
            returned_at = None
            overdue_days = 0
            fine_amount = 0
        else:
            delay = (i % 40) - 10
            returned_at = due_at + timedelta(days=delay)
            overdue_days = calculate_overdue(due_at, returned_at)
            fine_amount = calculate_fine(overdue_days)

        loans.append(
            {
                "id": i + 1,
                "reader_id": reader_id,
                "copy_id": copy_id,
                "issued_at": issued_at,
                "due_at": due_at,
                "returned_at": returned_at,
                "overdue_days": overdue_days,
                "fine_amount": fine_amount,
                "created_at": now,
            }
        )

    for i, status in enumerate(copy_status):
        copies[i]["status"] = status

    with engine.begin() as conn:
        conn.execute(text(f"SET search_path TO {settings.schema_name}, public"))
        conn.execute(
            User.__table__.insert(),
            [{"id": 1, "username": "demo", "password_hash": hash_password("demo"), "is_active": True}],
        )
        for batch in chunks(readers):
            conn.execute(Reader.__table__.insert(), batch)
        for batch in chunks(books):
            conn.execute(Book.__table__.insert(), batch)
        for batch in chunks(copies):
            conn.execute(Copy.__table__.insert(), batch)
        for batch in chunks(loans):
            conn.execute(Loan.__table__.insert(), batch)
        for table, n in (
            ("users", 1),
            ("readers", cfg["readers"]),
            ("books", cfg["books"]),
            ("copies", cfg["copies"]),
            ("loans", cfg["loans"]),
        ):
            conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}','id'), {n})"))

    with engine.connect() as conn:
        conn.execute(text(f"SET search_path TO {settings.schema_name}, public"))
        return {
            "users": conn.execute(text("SELECT count(*) FROM users")).scalar(),
            "readers": conn.execute(text("SELECT count(*) FROM readers")).scalar(),
            "books": conn.execute(text("SELECT count(*) FROM books")).scalar(),
            "copies": conn.execute(text("SELECT count(*) FROM copies")).scalar(),
            "loans": conn.execute(text("SELECT count(*) FROM loans")).scalar(),
        }


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
