"""Generate realistic, reproducible sample data (random seed fixed)."""
import random
from datetime import date, timedelta

random.seed(42)

DEPARTMENTS = [
    ("Engineering", "Bengaluru"), ("Human Resources", "Mumbai"),
    ("Sales", "Delhi"), ("Customer Support", "Patna"),
    ("Finance", "Mumbai"), ("Marketing", "Pune"),
]

# (title, min_salary, max_salary) per department; first entry = manager title
DEPT_TITLES = {
    "Engineering":      [("Engineering Manager", 90000, 160000), ("Software Engineer", 50000, 110000), ("QA Engineer", 40000, 80000)],
    "Human Resources":  [("HR Manager", 70000, 120000), ("HR Executive", 35000, 65000)],
    "Sales":            [("Sales Manager", 70000, 130000), ("Sales Executive", 30000, 70000)],
    "Customer Support": [("Support Manager", 55000, 95000), ("Support Associate", 25000, 50000)],
    "Finance":          [("Finance Manager", 80000, 140000), ("Accountant", 40000, 85000)],
    "Marketing":        [("Marketing Manager", 70000, 125000), ("Content Specialist", 35000, 75000)],
}
DEPT_SIZES = {"Engineering": 16, "Human Resources": 6, "Sales": 14,
              "Customer Support": 12, "Finance": 8, "Marketing": 8}

FIRST = ["Aarav", "Vivaan", "Aditya", "Rohan", "Karan", "Ishaan", "Neha", "Priya", "Anjali",
         "Sneha", "Pooja", "Kavya", "Riya", "Meera", "Arjun", "Rahul", "Sanjay", "Deepak",
         "Nisha", "Isha", "Tanvi", "Varun", "Manish", "Divya", "Amit", "Sunita", "Rajesh"]
LAST = ["Sharma", "Verma", "Gupta", "Singh", "Kumar", "Patel", "Mehta", "Jha", "Mishra",
        "Yadav", "Reddy", "Nair", "Iyer", "Das", "Roy", "Chopra", "Kapoor", "Joshi"]

ATT_START, ATT_END = date(2026, 7, 1), date(2026, 9, 30)
REVIEW_DATES = [date(2025, 12, 15), date(2026, 6, 15)]


def weekdays(start, end):
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def seed(conn):
    cur = conn.cursor()
    cur.executemany("INSERT INTO departments (dept_name, location) VALUES (?, ?)", DEPARTMENTS)
    dept_ids = {r["dept_name"]: r["dept_id"] for r in conn.execute("SELECT * FROM departments")}

    title_ids = {}
    for titles in DEPT_TITLES.values():
        for name, lo, hi in titles:
            cur.execute("INSERT INTO job_titles (title_name, min_salary, max_salary) VALUES (?, ?, ?)", (name, lo, hi))
            title_ids[name] = (cur.lastrowid, lo, hi)

    employees = []  # (emp_id, hire_date, reliability, manager_id)
    n = 0
    for dept, size in DEPT_SIZES.items():
        manager_id = None
        for i in range(size):
            n += 1
            is_mgr = i == 0
            title = DEPT_TITLES[dept][0][0] if is_mgr else random.choice(DEPT_TITLES[dept][1:])[0]
            tid, lo, hi = title_ids[title]
            first, last = random.choice(FIRST), random.choice(LAST)
            hire = date(2018, 1, 1) + timedelta(days=random.randint(0, (date(2026, 3, 31) - date(2018, 1, 1)).days))
            salary = round(random.uniform(lo, hi), -2)
            cur.execute(
                """INSERT INTO employees (first_name, last_name, email, phone, hire_date,
                   salary, dept_id, title_id, manager_id, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (first, last, f"{first}.{last}{n}@company.com".lower(),
                 f"+91 9{random.randint(100000000, 999999999)}", hire.isoformat(),
                 salary, dept_ids[dept], tid, manager_id,
                 random.choices(["Active", "On Leave", "Terminated"], [92, 5, 3])[0] if not is_mgr else "Active"),
            )
            eid = cur.lastrowid
            if is_mgr:
                manager_id = eid
            employees.append((eid, hire, random.uniform(0.80, 1.0), manager_id if not is_mgr else None))

    # Attendance: weekdays only, from max(hire date, window start)
    rows = []
    for eid, hire, reliability, _ in employees:
        for day in weekdays(max(ATT_START, hire), ATT_END):
            r = random.random()
            miss = (1 - reliability) * 0.5
            if r < miss:
                status, cin, cout = random.choice(["Absent", "Leave"]), None, None
            elif r < miss + (1 - reliability) * 0.6:
                status = "Late"
                cin = f"09:{random.randint(20, 59)}"
                cout = "18:%02d" % random.randint(0, 30)
            elif r < miss + (1 - reliability) * 0.6 + 0.01:
                status, cin, cout = "Half-Day", "09:%02d" % random.randint(0, 15), "13:%02d" % random.randint(0, 30)
            else:
                status = "Present"
                cin = "08:%02d" % random.randint(40, 59) if random.random() < 0.4 else "09:%02d" % random.randint(0, 15)
                cout = "17:%02d" % random.randint(30, 59)
            rows.append((eid, day.isoformat(), status, cin, cout))
    cur.executemany("INSERT INTO attendance (emp_id, att_date, status, check_in, check_out) VALUES (?, ?, ?, ?, ?)", rows)

    # Performance reviews (two cycles; skip cycles before hire)
    reviews = []
    for eid, hire, reliability, mgr in employees:
        for rd in REVIEW_DATES:
            if rd > hire + timedelta(days=90):
                base = 1 + reliability * 4  # reliable people tend to rate higher
                rating = max(1, min(5, round(random.gauss(base - 0.8, 0.7))))
                goals = max(20, min(100, round(rating * 18 + random.uniform(-8, 10), 1)))
                reviews.append((eid, mgr, rd.isoformat(), rating, goals, None))
    cur.executemany(
        """INSERT INTO performance_reviews (emp_id, reviewer_id, review_date, rating, goals_met_pct, comments)
           VALUES (?, ?, ?, ?, ?, ?)""", reviews)
    conn.commit()
    return {"employees": len(employees), "attendance": len(rows), "reviews": len(reviews)}
