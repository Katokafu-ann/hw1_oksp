from datetime import date

from app.business import (
    calculate_fine,
    calculate_overdue,
    can_issue_copy,
    can_issue_to_reader,
    due_date_from_issue,
)


def test_overdue_zero_when_returned_on_time():
    assert calculate_overdue(date(2026, 1, 10), date(2026, 1, 10)) == 0


def test_overdue_counts_days_after_due():
    assert calculate_overdue(date(2026, 1, 10), date(2026, 1, 15)) == 5


def test_fine_is_days_times_rate():
    assert calculate_fine(5, fine_per_day=10) == 50


def test_cannot_issue_to_reader_with_overdue():
    assert can_issue_to_reader(has_overdue_open_loans=True) is False
    assert can_issue_to_reader(has_overdue_open_loans=False) is True


def test_cannot_issue_busy_copy():
    assert can_issue_copy("available") is True
    assert can_issue_copy("on_loan") is False


def test_due_date_adds_loan_days():
    assert due_date_from_issue(date(2026, 1, 1), loan_days=14) == date(2026, 1, 15)
