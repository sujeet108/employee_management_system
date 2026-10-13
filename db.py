"""Database helpers: connection, schema creation, and validated write operations."""
import sqlite3
from pathlib import Path

import validators

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "ems.db"


class ValidationError(Exception):
    """Raised when input data fails validation (Python layer or DB layer)."""

    def __init__(self, errors):
        self.errors = errors if isinstance(errors, list) else [errors]
        super().__init__("; ".join(self.errors))


def get_connection(path=DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    """Create (or recreate) all tables, indexes, triggers and views."""
    conn.executescript((BASE_DIR / "schema.sql").read_text())
    conn.commit()


def _lookup_id(conn, table, id_col, name_col, value):
    row = conn.execute(
        f"SELECT {id_col} FROM {table} WHERE lower({name_col}) = lower(?)", (value,)
    ).fetchone()
    return row[0] if row else None


def _run_insert(conn, sql, params):
    """Execute an INSERT, translating DB constraint errors into ValidationError."""
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise ValidationError(f"Database rejected the record: {exc}") from exc


def add_employee(conn, data):
    """Validate (Python layer) then insert (DB layer enforces again)."""
    errors = validators.validate_employee(data)
    dept_id = _lookup_id(conn, "departments", "dept_id", "dept_name", data.get("department", ""))
    title_id = _lookup_id(conn, "job_titles", "title_id", "title_name", data.get("job_title", ""))
    if dept_id is None:
        errors.append(f"Unknown department: {data.get('department')!r}")
    if title_id is None:
        errors.append(f"Unknown job title: {data.get('job_title')!r}")
    if errors:
        raise ValidationError(errors)

    return _run_insert(
        conn,
        """INSERT INTO employees
           (first_name, last_name, email, phone, hire_date, salary, dept_id, title_id, manager_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["first_name"].strip(), data["last_name"].strip(),
            data["email"].strip().lower(), data.get("phone") or None,
            data["hire_date"], float(data["salary"]), dept_id, title_id,
            data.get("manager_id"),
        ),
    )


def mark_attendance(conn, data):
    errors = validators.validate_attendance(data)
    if errors:
        raise ValidationError(errors)
    return _run_insert(
        conn,
        "INSERT INTO attendance (emp_id, att_date, status, check_in, check_out) VALUES (?, ?, ?, ?, ?)",
        (data["emp_id"], data["att_date"], data["status"],
         data.get("check_in"), data.get("check_out")),
    )


def add_review(conn, data):
    errors = validators.validate_review(data)
    if errors:
        raise ValidationError(errors)
    return _run_insert(
        conn,
        """INSERT INTO performance_reviews
           (emp_id, reviewer_id, review_date, rating, goals_met_pct, comments)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (data["emp_id"], data.get("reviewer_id"), data["review_date"],
         int(data["rating"]), float(data["goals_met_pct"]), data.get("comments")),
    )
