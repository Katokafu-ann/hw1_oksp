from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.business import (
    calculate_fine,
    calculate_overdue,
    can_issue_copy,
    can_issue_to_reader,
    due_date_from_issue,
)
from app.models import Book, Copy, Loan, Reader


def reader_has_overdue(db: Session, reader_id: int, today: date | None = None) -> bool:
    today = today or date.today()
    loans = (
        db.query(Loan)
        .filter(Loan.reader_id == reader_id, Loan.returned_at.is_(None))
        .all()
    )
    for loan in loans:
        if calculate_overdue(loan.due_at, None, today) > 0:
            return True
    return False


def issue_loan(db: Session, reader_id: int, copy_id: int, issued_at: date | None = None) -> Loan:
    issued_at = issued_at or date.today()

    reader = db.get(Reader, reader_id)
    if reader is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reader not found")

    copy = db.get(Copy, copy_id)
    if copy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="copy not found")

    if not can_issue_copy(copy.status):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="copy is not available")

    if not can_issue_to_reader(reader_has_overdue(db, reader_id, issued_at)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="reader has overdue loans",
        )

    loan = Loan(
        reader_id=reader_id,
        copy_id=copy_id,
        issued_at=issued_at,
        due_at=due_date_from_issue(issued_at),
        returned_at=None,
        overdue_days=0,
        fine_amount=0,
    )
    copy.status = "on_loan"
    db.add(loan)
    db.commit()
    db.refresh(loan)
    return (
        db.query(Loan)
        .options(joinedload(Loan.reader), joinedload(Loan.copy).joinedload(Copy.book))
        .filter(Loan.id == loan.id)
        .one()
    )


def return_loan(db: Session, loan_id: int, returned_at: date | None = None) -> Loan:
    returned_at = returned_at or date.today()
    loan = (
        db.query(Loan)
        .options(joinedload(Loan.reader), joinedload(Loan.copy).joinedload(Copy.book))
        .filter(Loan.id == loan_id)
        .one_or_none()
    )
    if loan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="loan not found")
    if loan.returned_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="loan already returned")

    overdue_days = calculate_overdue(loan.due_at, returned_at)
    loan.returned_at = returned_at
    loan.overdue_days = overdue_days
    loan.fine_amount = calculate_fine(overdue_days)
    loan.copy.status = "available"
    db.commit()
    db.refresh(loan)
    return loan


def list_loans(
    db: Session,
    page: int = 1,
    size: int = 20,
    reader_id: int | None = None,
    status_filter: str | None = None,
    q: str | None = None,
) -> tuple[list[Loan], int]:
    if page < 1 or size < 1 or size > 200:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid page or size")

    base = db.query(Loan.id)

    if reader_id is not None:
        base = base.filter(Loan.reader_id == reader_id)

    if status_filter == "open":
        base = base.filter(Loan.returned_at.is_(None))
    elif status_filter == "returned":
        base = base.filter(Loan.returned_at.is_not(None))
    elif status_filter == "overdue":
        today = date.today()
        base = base.filter(Loan.returned_at.is_(None), Loan.due_at < today)
    elif status_filter is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid status")

    if q:
        pattern = f"%{q}%"
        base = (
            base.join(Reader, Reader.id == Loan.reader_id)
            .join(Copy, Copy.id == Loan.copy_id)
            .join(Book, Book.id == Copy.book_id)
            .filter(
                (Reader.full_name.ilike(pattern))
                | (Reader.ticket_number.ilike(pattern))
                | (Book.title.ilike(pattern))
                | (Copy.inventory_number.ilike(pattern))
            )
        )

    total = base.with_entities(func.count(func.distinct(Loan.id))).scalar() or 0
    id_rows = (
        base.with_entities(Loan.id)
        .order_by(Loan.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    ids = [row[0] for row in id_rows]
    if not ids:
        return [], total

    items = (
        db.query(Loan)
        .options(joinedload(Loan.reader), joinedload(Loan.copy).joinedload(Copy.book))
        .filter(Loan.id.in_(ids))
        .all()
    )
    by_id = {loan.id: loan for loan in items}
    ordered = [by_id[i] for i in ids if i in by_id]
    return ordered, total


def get_loan(db: Session, loan_id: int) -> Loan:
    loan = (
        db.query(Loan)
        .options(joinedload(Loan.reader), joinedload(Loan.copy).joinedload(Copy.book))
        .filter(Loan.id == loan_id)
        .one_or_none()
    )
    if loan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="loan not found")
    return loan


def build_summary(db: Session) -> dict:
    """Сводка считается по всем данным (прямолинейно — узкое место для замеров)."""
    open_loans = (
        db.query(Loan)
        .options(joinedload(Loan.copy).joinedload(Copy.book))
        .filter(Loan.returned_at.is_(None))
        .all()
    )

    today = date.today()
    copies_on_hand = len(open_loans)
    overdue_on_hand = 0
    for loan in open_loans:
        if calculate_overdue(loan.due_at, None, today) > 0:
            overdue_on_hand += 1

    # Популярность книг: все выдачи, подсчёт в приложении
    all_loans = (
        db.query(Loan)
        .options(joinedload(Loan.copy).joinedload(Copy.book))
        .all()
    )
    counts: dict[int, dict] = {}
    total_fines = 0
    for loan in all_loans:
        total_fines += loan.fine_amount
        book = loan.copy.book
        entry = counts.setdefault(
            book.id,
            {"book_id": book.id, "title": book.title, "author": book.author, "loan_count": 0},
        )
        entry["loan_count"] += 1

    popular = sorted(counts.values(), key=lambda x: (-x["loan_count"], x["title"]))[:10]

    return {
        "copies_on_hand": copies_on_hand,
        "overdue_on_hand": overdue_on_hand,
        "popular_books": popular,
        "total_loans": len(all_loans),
        "total_fines": total_fines,
    }
