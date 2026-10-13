"""Python-layer data validation. Catches bad input BEFORE it reaches the database.
(The schema's CHECK constraints and triggers act as a second line of defence.)"""
import re
from datetime import date, datetime

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9 \-]{6,14}$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'\-]*$")
ATTENDANCE_STATUSES = {"Present", "Late", "Absent", "Leave", "Half-Day"}


def parse_date(value):
    """Return a date for 'YYYY-MM-DD' strings, else None."""
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def parse_time(value):
    try:
        return datetime.strptime(str(value), "%H:%M").time()
    except (ValueError, TypeError):
        return None


def validate_employee(d):
    errors = []
    for field in ("first_name", "last_name"):
        v = (d.get(field) or "").strip()
        if not v:
            errors.append(f"{field} is required")
        elif not NAME_RE.match(v):
            errors.append(f"{field} contains invalid characters")

    if not EMAIL_RE.match((d.get("email") or "").strip()):
        errors.append("email is not a valid address")

    phone = d.get("phone")
    if phone and not PHONE_RE.match(str(phone).strip()):
        errors.append("phone must be 7-15 digits (optional leading +)")

    hired = parse_date(d.get("hire_date"))
    if hired is None:
        errors.append("hire_date must be a real date in YYYY-MM-DD format")
    elif hired > date.today():
        errors.append("hire_date cannot be in the future")

    try:
        if float(d.get("salary")) <= 0:
            errors.append("salary must be greater than 0")
    except (TypeError, ValueError):
        errors.append("salary must be a number")
    return errors


def validate_attendance(d):
    errors = []
    if not isinstance(d.get("emp_id"), int):
        errors.append("emp_id must be an integer")
    day = parse_date(d.get("att_date"))
    if day is None:
        errors.append("att_date must be a real date in YYYY-MM-DD format")
    elif day > date.today():
        errors.append("att_date cannot be in the future")
    if d.get("status") not in ATTENDANCE_STATUSES:
        errors.append(f"status must be one of {sorted(ATTENDANCE_STATUSES)}")

    cin, cout = d.get("check_in"), d.get("check_out")
    t_in = parse_time(cin) if cin else None
    t_out = parse_time(cout) if cout else None
    if cin and t_in is None:
        errors.append("check_in must be HH:MM (24h)")
    if cout and t_out is None:
        errors.append("check_out must be HH:MM (24h)")
    if t_in and t_out and t_out <= t_in:
        errors.append("check_out must be after check_in")
    if d.get("status") in ("Absent", "Leave") and cin:
        errors.append("check_in is not allowed when status is Absent or Leave")
    return errors


def validate_review(d):
    errors = []
    if not isinstance(d.get("emp_id"), int):
        errors.append("emp_id must be an integer")
    if parse_date(d.get("review_date")) is None:
        errors.append("review_date must be a real date in YYYY-MM-DD format")
    try:
        if int(d.get("rating")) not in range(1, 6):
            errors.append("rating must be between 1 and 5")
    except (TypeError, ValueError):
        errors.append("rating must be an integer between 1 and 5")
    try:
        if not 0 <= float(d.get("goals_met_pct")) <= 100:
            errors.append("goals_met_pct must be between 0 and 100")
    except (TypeError, ValueError):
        errors.append("goals_met_pct must be a number between 0 and 100")
    if d.get("reviewer_id") is not None and d.get("reviewer_id") == d.get("emp_id"):
        errors.append("an employee cannot review themselves")
    return errors
