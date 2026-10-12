from datetime import date, timedelta

from app.config import settings


def calculate_overdue(due_at: date, returned_at: date | None, today: date | None = None) -> int:
    """Разница между сроком возврата и фактической датой (или сегодня, если ещё на руках)."""
    end = returned_at if returned_at is not None else (today or date.today())
    delta = (end - due_at).days
    return max(0, delta)


def calculate_fine(overdue_days: int, fine_per_day: int | None = None) -> int:
    """Размер штрафа по числу дней просрочки."""
    rate = fine_per_day if fine_per_day is not None else settings.fine_per_day
    return overdue_days * rate


def can_issue_to_reader(has_overdue_open_loans: bool) -> bool:
    """Выдача запрещена, если у читателя есть просроченные незакрытые выдачи."""
    return not has_overdue_open_loans


def can_issue_copy(copy_status: str) -> bool:
    """Выдача возможна только если экземпляр свободен."""
    return copy_status == "available"


def due_date_from_issue(issued_at: date, loan_days: int | None = None) -> date:
    days = loan_days if loan_days is not None else settings.loan_days
    return issued_at + timedelta(days=days)
