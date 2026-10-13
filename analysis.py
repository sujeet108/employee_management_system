"""Load named queries from queries.sql, run them, pretty-print or export to CSV."""
import csv
import re
from pathlib import Path

QUERY_FILE = Path(__file__).parent / "queries.sql"


def load_queries():
    text = QUERY_FILE.read_text()
    parts = re.split(r"^-- name:\s*(\w+)\s*$", text, flags=re.MULTILINE)
    # parts = [preamble, name1, body1, name2, body2, ...]
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def run_query(conn, name):
    queries = load_queries()
    if name not in queries:
        raise KeyError(f"Unknown query {name!r}. Available: {', '.join(queries)}")
    cur = conn.execute(queries[name])
    cols = [c[0] for c in cur.description]
    return cols, cur.fetchall()


def format_table(cols, rows, max_rows=25):
    shown = rows[:max_rows]
    widths = [max(len(str(c)), *(len(str(r[i])) for r in shown)) if shown else len(str(c))
              for i, c in enumerate(cols)]
    line = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    out = [line, "| " + " | ".join(str(c).ljust(w) for c, w in zip(cols, widths)) + " |", line]
    for r in shown:
        out.append("| " + " | ".join(str(v).ljust(w) for v, w in zip(r, widths)) + " |")
    out.append(line)
    if len(rows) > max_rows:
        out.append(f"... {len(rows) - max_rows} more rows")
    return "\n".join(out)


def print_report(conn, name):
    cols, rows = run_query(conn, name)
    print(f"\n=== {name.replace('_', ' ').title()} ===")
    print(format_table(cols, rows))


def export_csv(conn, name, out_dir):
    cols, rows = run_query(conn, name)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows([tuple(r) for r in rows])
    return path
