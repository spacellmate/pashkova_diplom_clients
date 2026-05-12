import os
import sqlite3
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "data.db")))
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-me-please")

DEFAULT_VISIT_COUNT = 70812
DEFAULT_ORDER_COUNT = 2212

app = Flask(__name__, template_folder="templates")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def column_exists(conn, table_name: str, column_name: str) -> bool:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cur.fetchall())


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    has_district = column_exists(conn, "leads", "district")
    has_diet = column_exists(conn, "leads", "diet")

    if has_district or has_diet:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS leads_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            INSERT INTO leads_new (id, name, phone, created_at)
            SELECT id, name, phone, created_at
            FROM leads
            """
        )
        cur.execute("DROP TABLE leads")
        cur.execute("ALTER TABLE leads_new RENAME TO leads")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS counters (
            key TEXT PRIMARY KEY,
            value INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    cur.execute("INSERT OR IGNORE INTO counters (key, value) VALUES ('visits', ?)", (DEFAULT_VISIT_COUNT,))
    cur.execute("INSERT OR IGNORE INTO counters (key, value) VALUES ('orders', ?)", (DEFAULT_ORDER_COUNT,))

    conn.commit()
    conn.close()


def get_counter(key: str, default: int) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM counters WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row["value"] if row else default


def increment_counter(key: str, default: int) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO counters (key, value) VALUES (?, ?)", (key, default))
    cur.execute("UPDATE counters SET value = value + 1 WHERE key = ?", (key,))
    conn.commit()
    cur.execute("SELECT value FROM counters WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row["value"] if row else default


@app.route("/")
def index():
    visit_count = increment_counter("visits", DEFAULT_VISIT_COUNT)
    order_count = get_counter("orders", DEFAULT_ORDER_COUNT)
    return render_template("klient-no-x5.html", visit_count=visit_count, order_count=order_count)


@app.route("/api/counters")
def api_counters():
    return jsonify({
        "visits": get_counter("visits", DEFAULT_VISIT_COUNT),
        "orders": get_counter("orders", DEFAULT_ORDER_COUNT),
    })


@app.route("/submit", methods=["POST"])
def submit():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()

    wants_json = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )

    if not name or not phone:
        if wants_json:
            return jsonify({"ok": False, "error": "Заполните имя и телефон"}), 400
        return redirect(url_for("index"))

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO leads (name, phone, created_at)
        VALUES (?, ?, ?)
        """,
        (name, phone, datetime.utcnow().isoformat())
    )
    cur.execute("INSERT OR IGNORE INTO counters (key, value) VALUES ('orders', ?)", (DEFAULT_ORDER_COUNT,))
    cur.execute("UPDATE counters SET value = value + 1 WHERE key = 'orders'")
    conn.commit()
    cur.execute("SELECT value FROM counters WHERE key = 'orders'")
    order_row = cur.fetchone()
    conn.close()

    order_count = order_row["value"] if order_row else DEFAULT_ORDER_COUNT

    if wants_json:
        return jsonify({"ok": True, "order_count": order_count})
    return redirect(url_for("index"))


@app.route("/admin/leads")
def admin_leads():
    token = request.args.get("token", "")
    if token != ADMIN_TOKEN:
        return "Forbidden", 403

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, phone, created_at
        FROM leads
        ORDER BY id DESC
        """
    )
    leads = cur.fetchall()
    conn.close()

    visit_count = get_counter("visits", DEFAULT_VISIT_COUNT)
    order_count = get_counter("orders", DEFAULT_ORDER_COUNT)

    rows = []
    for lead in leads:
        rows.append(f"""
            <tr>
                <td>{lead['id']}</td>
                <td>{lead['name']}</td>
                <td>{lead['phone']}</td>
                <td>{lead['created_at']}</td>
            </tr>
        """)

    return f"""
    <!doctype html>
    <html lang="ru">
    <head>
        <meta charset="utf-8">
        <title>Заявки</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f7f7f7; color: #222; }}
            .wrap {{ max-width: 1100px; margin: 0 auto; background: white; padding: 24px; border-radius: 16px; box-shadow: 0 8px 30px rgba(0,0,0,.08); }}
            h1 {{ margin-top: 0; }}
            .meta {{ margin-bottom: 20px; color: #555; display: flex; gap: 24px; flex-wrap: wrap; }}
            table {{ width: 100%; border-collapse: collapse; background: white; }}
            th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; font-size: 14px; vertical-align: top; }}
            th {{ background: #f0f0f0; }}
            tr:nth-child(even) {{ background: #fafafa; }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <h1>Заявки с сайта</h1>
            <div class="meta">
                <div>Всего визитов: <strong>{visit_count}</strong></div>
                <div>Всего заявок по счетчику: <strong>{order_count}</strong></div>
                <div>Реальных заявок в базе: <strong>{len(leads)}</strong></div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Имя</th>
                        <th>Телефон</th>
                        <th>Дата</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows) if rows else '<tr><td colspan="4">Пока нет заявок</td></tr>'}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
else:
    init_db()