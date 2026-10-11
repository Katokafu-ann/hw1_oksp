from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.business import due_date_from_issue
from app.db import Base, get_db
from app.main import app
from app.models import Book, Copy, Loan, Reader, User


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = TestingSession()

    db.add(User(username="demo", password_hash=hash_password("demo"), is_active=True))
    reader_ok = Reader(
        full_name="Иван Иванов",
        ticket_number="T-1",
        email="ivan@test.local",
        registered_at=date(2024, 1, 1),
    )
    reader_debt = Reader(
        full_name="Пётр Должников",
        ticket_number="T-2",
        email="petr@test.local",
        registered_at=date(2024, 1, 1),
    )
    book = Book(title="Тест", author="Автор", isbn="978-0", year=2020, description="d")
    db.add_all([reader_ok, reader_debt, book])
    db.flush()

    copy_free = Copy(book_id=book.id, inventory_number="INV-1", status="available")
    copy_busy = Copy(book_id=book.id, inventory_number="INV-2", status="on_loan")
    db.add_all([copy_free, copy_busy])
    db.flush()

    overdue = Loan(
        reader_id=reader_debt.id,
        copy_id=copy_busy.id,
        issued_at=date(2025, 1, 1),
        due_at=date(2025, 1, 15),
        returned_at=None,
        overdue_days=0,
        fine_amount=0,
    )
    db.add(overdue)
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, db, {
            "reader_ok": reader_ok.id,
            "reader_debt": reader_debt.id,
            "copy_free": copy_free.id,
            "copy_busy": copy_busy.id,
            "overdue_loan": overdue.id,
        }

    app.dependency_overrides.clear()
    db.close()


def auth_headers(client: TestClient) -> dict:
    response = client.post("/api/auth/login", json={"username": "demo", "password": "demo"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_list_requires_authorization(client):
    test_client, _db, _ids = client
    response = test_client.get("/api/loans")
    assert response.status_code == 401


def test_list_returns_page(client):
    test_client, _db, _ids = client
    response = test_client.get("/api/loans?page=1&size=20", headers=auth_headers(test_client))
    assert response.status_code == 200
    body = response.json()
    assert "items" in body and "total" in body
    assert body["page"] == 1


def test_issue_forbidden_when_reader_has_overdue(client):
    test_client, _db, ids = client
    response = test_client.post(
        "/api/loans",
        headers=auth_headers(test_client),
        json={"reader_id": ids["reader_debt"], "copy_id": ids["copy_free"], "issued_at": "2026-01-01"},
    )
    assert response.status_code == 409
    assert "overdue" in response.json()["detail"]


def test_issue_and_return_with_fine(client):
    test_client, _db, ids = client
    headers = auth_headers(test_client)
    issued = test_client.post(
        "/api/loans",
        headers=headers,
        json={"reader_id": ids["reader_ok"], "copy_id": ids["copy_free"], "issued_at": "2026-01-01"},
    )
    assert issued.status_code == 201
    loan_id = issued.json()["id"]
    assert issued.json()["due_at"] == due_date_from_issue(date(2026, 1, 1)).isoformat()

    returned = test_client.post(
        f"/api/loans/{loan_id}/return",
        headers=headers,
        json={"returned_at": "2026-01-25"},
    )
    assert returned.status_code == 200
    body = returned.json()
    assert body["overdue_days"] == 10
    assert body["fine_amount"] == 100


def test_summary_requires_auth_and_returns_fields(client):
    test_client, _db, _ids = client
    assert test_client.get("/api/summary").status_code == 401
    response = test_client.get("/api/summary", headers=auth_headers(test_client))
    assert response.status_code == 200
    body = response.json()
    assert "copies_on_hand" in body
    assert "overdue_on_hand" in body
    assert "popular_books" in body
