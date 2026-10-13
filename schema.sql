-- =====================================================================
-- Employee Management System - Normalized Relational Schema (3NF)
-- Engine: SQLite (portable to MySQL/PostgreSQL with minor syntax changes)
-- =====================================================================
PRAGMA foreign_keys = ON;

DROP VIEW    IF EXISTS v_dept_headcount;
DROP VIEW    IF EXISTS v_monthly_attendance;
DROP TABLE   IF EXISTS performance_reviews;
DROP TABLE   IF EXISTS attendance;
DROP TABLE   IF EXISTS employees;
DROP TABLE   IF EXISTS job_titles;
DROP TABLE   IF EXISTS departments;

-- ---------------------------------------------------------------------
-- 1. departments
-- ---------------------------------------------------------------------
CREATE TABLE departments (
    dept_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    dept_name  TEXT NOT NULL UNIQUE CHECK (length(trim(dept_name)) > 0),
    location   TEXT
);

-- ---------------------------------------------------------------------
-- 2. job_titles  (salary bands live here -> avoids redundancy in employees)
-- ---------------------------------------------------------------------
CREATE TABLE job_titles (
    title_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    title_name  TEXT NOT NULL UNIQUE,
    min_salary  REAL NOT NULL CHECK (min_salary > 0),
    max_salary  REAL NOT NULL,
    CHECK (max_salary >= min_salary)
);

-- ---------------------------------------------------------------------
-- 3. employees
-- ---------------------------------------------------------------------
CREATE TABLE employees (
    emp_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name  TEXT NOT NULL CHECK (length(trim(first_name)) > 0),
    last_name   TEXT NOT NULL CHECK (length(trim(last_name)) > 0),
    email       TEXT NOT NULL UNIQUE CHECK (email LIKE '_%@_%._%'),
    phone       TEXT CHECK (phone IS NULL OR phone GLOB '[0-9+][0-9 -]*'),
    hire_date   TEXT NOT NULL
                CHECK (hire_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    salary      REAL NOT NULL CHECK (salary > 0),
    dept_id     INTEGER NOT NULL,
    title_id    INTEGER NOT NULL,
    manager_id  INTEGER,
    status      TEXT NOT NULL DEFAULT 'Active'
                CHECK (status IN ('Active', 'On Leave', 'Terminated')),
    FOREIGN KEY (dept_id)    REFERENCES departments(dept_id) ON DELETE RESTRICT,
    FOREIGN KEY (title_id)   REFERENCES job_titles(title_id) ON DELETE RESTRICT,
    FOREIGN KEY (manager_id) REFERENCES employees(emp_id)    ON DELETE SET NULL,
    CHECK (manager_id IS NULL OR manager_id <> emp_id)
);

-- ---------------------------------------------------------------------
-- 4. attendance  (one row per employee per day)
-- ---------------------------------------------------------------------
CREATE TABLE attendance (
    att_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_id     INTEGER NOT NULL,
    att_date   TEXT NOT NULL
               CHECK (att_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    status     TEXT NOT NULL
               CHECK (status IN ('Present', 'Late', 'Absent', 'Leave', 'Half-Day')),
    check_in   TEXT CHECK (check_in  IS NULL OR check_in  GLOB '[0-2][0-9]:[0-5][0-9]'),
    check_out  TEXT CHECK (check_out IS NULL OR check_out GLOB '[0-2][0-9]:[0-5][0-9]'),
    UNIQUE (emp_id, att_date),
    CHECK (check_in IS NULL OR check_out IS NULL OR check_out > check_in),
    CHECK (status NOT IN ('Absent', 'Leave') OR check_in IS NULL),
    FOREIGN KEY (emp_id) REFERENCES employees(emp_id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- 5. performance_reviews
-- ---------------------------------------------------------------------
CREATE TABLE performance_reviews (
    review_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_id        INTEGER NOT NULL,
    reviewer_id   INTEGER,
    review_date   TEXT NOT NULL
                  CHECK (review_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    rating        INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    goals_met_pct REAL    NOT NULL CHECK (goals_met_pct BETWEEN 0 AND 100),
    comments      TEXT,
    UNIQUE (emp_id, review_date),
    CHECK (reviewer_id IS NULL OR reviewer_id <> emp_id),
    FOREIGN KEY (emp_id)      REFERENCES employees(emp_id) ON DELETE CASCADE,
    FOREIGN KEY (reviewer_id) REFERENCES employees(emp_id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- Indexes for the most common join / filter columns
-- ---------------------------------------------------------------------
CREATE INDEX idx_emp_dept      ON employees(dept_id);
CREATE INDEX idx_emp_manager   ON employees(manager_id);
CREATE INDEX idx_att_emp_date  ON attendance(emp_id, att_date);
CREATE INDEX idx_att_date      ON attendance(att_date);
CREATE INDEX idx_rev_emp       ON performance_reviews(emp_id);

-- ---------------------------------------------------------------------
-- Data-validation triggers (rules a CHECK constraint cannot express
-- because they need to look at another table)
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_emp_salary_band_ins
BEFORE INSERT ON employees
WHEN NEW.salary < (SELECT min_salary FROM job_titles WHERE title_id = NEW.title_id)
  OR NEW.salary > (SELECT max_salary FROM job_titles WHERE title_id = NEW.title_id)
BEGIN
    SELECT RAISE(ABORT, 'Salary is outside the allowed band for this job title');
END;

CREATE TRIGGER trg_emp_salary_band_upd
BEFORE UPDATE OF salary, title_id ON employees
WHEN NEW.salary < (SELECT min_salary FROM job_titles WHERE title_id = NEW.title_id)
  OR NEW.salary > (SELECT max_salary FROM job_titles WHERE title_id = NEW.title_id)
BEGIN
    SELECT RAISE(ABORT, 'Salary is outside the allowed band for this job title');
END;

CREATE TRIGGER trg_att_after_hire
BEFORE INSERT ON attendance
WHEN NEW.att_date < (SELECT hire_date FROM employees WHERE emp_id = NEW.emp_id)
BEGIN
    SELECT RAISE(ABORT, 'Attendance date is before the employee hire date');
END;

CREATE TRIGGER trg_review_after_hire
BEFORE INSERT ON performance_reviews
WHEN NEW.review_date < (SELECT hire_date FROM employees WHERE emp_id = NEW.emp_id)
BEGIN
    SELECT RAISE(ABORT, 'Review date is before the employee hire date');
END;

-- ---------------------------------------------------------------------
-- Reporting views
-- ---------------------------------------------------------------------
CREATE VIEW v_dept_headcount AS
SELECT d.dept_id, d.dept_name,
       COUNT(e.emp_id) AS headcount
FROM departments d
LEFT JOIN employees e ON e.dept_id = d.dept_id AND e.status <> 'Terminated'
GROUP BY d.dept_id, d.dept_name;

CREATE VIEW v_monthly_attendance AS
SELECT d.dept_name,
       strftime('%Y-%m', a.att_date) AS month,
       COUNT(*) AS records,
       SUM(CASE WHEN a.status IN ('Present','Late','Half-Day') THEN 1 ELSE 0 END) AS attended,
       ROUND(100.0 * SUM(CASE WHEN a.status IN ('Present','Late','Half-Day') THEN 1 ELSE 0 END)
             / COUNT(*), 2) AS attendance_pct
FROM attendance a
JOIN employees   e ON e.emp_id  = a.emp_id
JOIN departments d ON d.dept_id = e.dept_id
GROUP BY d.dept_name, strftime('%Y-%m', a.att_date);
