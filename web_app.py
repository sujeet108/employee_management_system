"""Web interface for the Employee Management System (Python standard library only).

Run:   python web_app.py
Then open  http://127.0.0.1:5000  in Google Chrome.
"""
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import analysis
import db
import seed_data

STATIC = Path(__file__).parent / "static"
PORT = 5000


def ensure_db():
    """First run: create the database and load sample data."""
    if not db.DB_PATH.exists():
        conn = db.get_connection()
        db.init_db(conn)
        seed_data.seed(conn)
        conn.close()
        print("Database created with sample data.")


def rows(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quieter console
        pass

    # ---------- helpers ----------
    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, ctype):
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ---------- GET ----------
    def do_GET(self):
        url = urlparse(self.path)
        conn = db.get_connection()
        try:
            if url.path in ("/", "/index.html"):
                return self.send_file(STATIC / "index.html", "text/html; charset=utf-8")

            if url.path == "/api/summary":
                s = rows(conn, """SELECT
                    (SELECT COUNT(*) FROM employees WHERE status='Active') AS active_employees,
                    (SELECT COUNT(*) FROM departments) AS departments,
                    (SELECT ROUND(100.0*SUM(status IN ('Present','Late','Half-Day'))/COUNT(*),2) FROM attendance) AS attendance_pct,
                    (SELECT ROUND(AVG(rating),2) FROM performance_reviews) AS avg_rating""")[0]
                out = {"kpi": s}
                for key in ("headcount_by_department", "attendance_rate_by_department", "monthly_attendance_trend"):
                    cols, data = analysis.run_query(conn, key)
                    out[key] = [dict(zip(cols, tuple(r))) for r in data]
                return self.send_json(out)

            if url.path == "/api/reports":
                return self.send_json(list(analysis.load_queries()))

            if url.path.startswith("/api/report/"):
                name = url.path.rsplit("/", 1)[1]
                try:
                    cols, data = analysis.run_query(conn, name)
                except KeyError:
                    return self.send_json({"errors": ["Unknown report"]}, 404)
                return self.send_json({"columns": cols, "rows": [list(r) for r in data]})

            if url.path == "/api/lookups":
                return self.send_json({
                    "departments": [r["dept_name"] for r in rows(conn, "SELECT dept_name FROM departments ORDER BY 1")],
                    "titles": [r["title_name"] for r in rows(conn, "SELECT title_name FROM job_titles ORDER BY 1")]})

            if url.path == "/api/employees":
                q = "%" + parse_qs(url.query).get("q", [""])[0].strip() + "%"
                return self.send_json(rows(conn, """
                    SELECT e.emp_id, e.first_name || ' ' || e.last_name AS name, e.email,
                           d.dept_name AS department, t.title_name AS job_title,
                           e.hire_date, e.salary, e.status
                    FROM employees e
                    JOIN departments d ON d.dept_id = e.dept_id
                    JOIN job_titles  t ON t.title_id = e.title_id
                    WHERE e.first_name || ' ' || e.last_name LIKE ? OR e.email LIKE ? OR d.dept_name LIKE ?
                    ORDER BY e.emp_id DESC LIMIT 200""", (q, q, q)))

            self.send_json({"errors": ["Not found"]}, 404)
        finally:
            conn.close()

    # ---------- POST ----------
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self.send_json({"errors": ["Invalid JSON"]}, 400)

        def to_int(key):
            v = data.get(key)
            data[key] = int(v) if v not in (None, "") else None

        conn = db.get_connection()
        try:
            path = urlparse(self.path).path
            try:
                if path == "/api/employees":
                    to_int("manager_id")
                    new_id = db.add_employee(conn, data)
                elif path == "/api/attendance":
                    to_int("emp_id")
                    data["check_in"] = data.get("check_in") or None
                    data["check_out"] = data.get("check_out") or None
                    new_id = db.mark_attendance(conn, data)
                elif path == "/api/reviews":
                    to_int("emp_id")
                    to_int("reviewer_id")
                    new_id = db.add_review(conn, data)
                else:
                    return self.send_json({"errors": ["Not found"]}, 404)
            except ValueError:
                return self.send_json({"errors": ["ID fields must be whole numbers"]}, 400)
            except db.ValidationError as exc:
                return self.send_json({"errors": exc.errors}, 400)
            self.send_json({"ok": True, "id": new_id})
        finally:
            conn.close()


def main():
    ensure_db()
    open_browser = "--no-browser" not in sys.argv
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"Server running at {url}  (press Ctrl+C to stop)")
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
