"""Command-line interface for the Employee Management System.

Examples
  python main.py setup                      # create schema + load sample data
  python main.py report                     # run every analysis query
  python main.py report headcount_by_department
  python main.py list-reports
  python main.py add-employee --first Asha --last Rao --email asha.rao@company.com \
         --hire-date 2026-01-10 --salary 45000 --dept "Customer Support" --title "Support Associate"
  python main.py mark-attendance --emp-id 1 --date 2026-10-01 --status Present --check-in 09:05 --check-out 18:00
  python main.py add-review --emp-id 1 --reviewer-id 2 --date 2026-06-30 --rating 4 --goals 85
  python main.py export --out exports
"""
import argparse
import sys

import analysis
import db
import seed_data


def build_parser():
    p = argparse.ArgumentParser(description="Employee Management System")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("setup", help="create the database and load sample data")
    sub.add_parser("init", help="create an empty database (no sample data)")
    sub.add_parser("list-reports", help="list available analysis queries")

    r = sub.add_parser("report", help="run one analysis query, or all if none given")
    r.add_argument("name", nargs="?")

    e = sub.add_parser("add-employee", help="add an employee (validated)")
    e.add_argument("--first", required=True)
    e.add_argument("--last", required=True)
    e.add_argument("--email", required=True)
    e.add_argument("--phone")
    e.add_argument("--hire-date", required=True)
    e.add_argument("--salary", required=True)
    e.add_argument("--dept", required=True)
    e.add_argument("--title", required=True)
    e.add_argument("--manager-id", type=int)

    a = sub.add_parser("mark-attendance", help="record attendance (validated)")
    a.add_argument("--emp-id", type=int, required=True)
    a.add_argument("--date", required=True)
    a.add_argument("--status", required=True)
    a.add_argument("--check-in")
    a.add_argument("--check-out")

    v = sub.add_parser("add-review", help="add a performance review (validated)")
    v.add_argument("--emp-id", type=int, required=True)
    v.add_argument("--reviewer-id", type=int)
    v.add_argument("--date", required=True)
    v.add_argument("--rating", required=True)
    v.add_argument("--goals", required=True)
    v.add_argument("--comments")

    x = sub.add_parser("export", help="export every report to CSV")
    x.add_argument("--out", default="exports")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    conn = db.get_connection()
    try:
        if args.cmd in ("setup", "init"):
            db.init_db(conn)
            print("Database created.")
            if args.cmd == "setup":
                print("Sample data loaded:", seed_data.seed(conn))
        elif args.cmd == "list-reports":
            print("\n".join(analysis.load_queries()))
        elif args.cmd == "report":
            names = [args.name] if args.name else list(analysis.load_queries())
            for n in names:
                analysis.print_report(conn, n)
        elif args.cmd == "add-employee":
            new_id = db.add_employee(conn, {
                "first_name": args.first, "last_name": args.last, "email": args.email,
                "phone": args.phone, "hire_date": args.hire_date, "salary": args.salary,
                "department": args.dept, "job_title": args.title, "manager_id": args.manager_id})
            print(f"Employee added with emp_id={new_id}")
        elif args.cmd == "mark-attendance":
            db.mark_attendance(conn, {
                "emp_id": args.emp_id, "att_date": args.date, "status": args.status,
                "check_in": args.check_in, "check_out": args.check_out})
            print("Attendance recorded.")
        elif args.cmd == "add-review":
            db.add_review(conn, {
                "emp_id": args.emp_id, "reviewer_id": args.reviewer_id, "review_date": args.date,
                "rating": args.rating, "goals_met_pct": args.goals, "comments": args.comments})
            print("Review recorded.")
        elif args.cmd == "export":
            for n in analysis.load_queries():
                print("Wrote", analysis.export_csv(conn, n, args.out))
    except db.ValidationError as exc:
        print("Validation failed:")
        for err in exc.errors:
            print("  -", err)
        return 1
    except KeyError as exc:
        print(exc)
        return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
