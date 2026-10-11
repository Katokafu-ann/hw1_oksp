from datetime import date, datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ReaderOut(BaseModel):
    id: int
    full_name: str
    ticket_number: str
    email: str
    registered_at: date

    model_config = {"from_attributes": True}


class BookOut(BaseModel):
    id: int
    title: str
    author: str
    isbn: str
    year: int
    description: str

    model_config = {"from_attributes": True}


class CopyOut(BaseModel):
    id: int
    book_id: int
    inventory_number: str
    status: str
    book: BookOut | None = None

    model_config = {"from_attributes": True}


class LoanOut(BaseModel):
    id: int
    reader_id: int
    copy_id: int
    issued_at: date
    due_at: date
    returned_at: date | None
    overdue_days: int
    fine_amount: int
    created_at: datetime
    reader: ReaderOut | None = None
    copy: CopyOut | None = None

    model_config = {"from_attributes": True}


class LoanCreate(BaseModel):
    reader_id: int
    copy_id: int
    issued_at: date | None = None


class LoanReturn(BaseModel):
    returned_at: date | None = None


class PaginatedLoans(BaseModel):
    items: list[LoanOut]
    total: int
    page: int
    size: int


class PopularBook(BaseModel):
    book_id: int
    title: str
    author: str
    loan_count: int


class SummaryOut(BaseModel):
    copies_on_hand: int
    overdue_on_hand: int
    popular_books: list[PopularBook]
    total_loans: int
    total_fines: int


class ErrorOut(BaseModel):
    detail: str = Field(..., examples=["copy is not available"])
