from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import create_token, get_current_user, hash_password, verify_password
from app.db import get_db
from app.models import User
from app.schemas import (
    LoanCreate,
    LoanOut,
    LoanReturn,
    LoginRequest,
    PaginatedLoans,
    SummaryOut,
    TokenResponse,
)
from app import services


router = APIRouter(prefix="/api")


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    from fastapi import HTTPException, status

    user = db.query(User).filter(User.username == body.username).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    return TokenResponse(access_token=create_token(user.id))


@router.get("/loans", response_model=PaginatedLoans)
def list_loans(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    reader_id: int | None = None,
    status: str | None = Query(None, description="open | returned | overdue"),
    q: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    items, total = services.list_loans(db, page=page, size=size, reader_id=reader_id, status_filter=status, q=q)
    return PaginatedLoans(items=items, total=total, page=page, size=size)


@router.get("/loans/{loan_id}", response_model=LoanOut)
def get_loan(loan_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return services.get_loan(db, loan_id)


@router.post("/loans", response_model=LoanOut, status_code=201)
def create_loan(
    body: LoanCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return services.issue_loan(db, body.reader_id, body.copy_id, body.issued_at)


@router.post("/loans/{loan_id}/return", response_model=LoanOut)
def return_loan(
    loan_id: int,
    body: LoanReturn,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return services.return_loan(db, loan_id, body.returned_at)


@router.get("/summary", response_model=SummaryOut)
def summary(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return services.build_summary(db)


@router.get("/health")
def health():
    return {"status": "ok", "project": "anna_akulova"}
