import os
import sqlite3
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify

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


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            district TEXT,
            diet TEXT,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS counters (
            key TEXT PRIMARY KEY,
            value INTEGER NOT NULL DEFAULT 0
        )
    """)

    cur.execute(
        "INSERT OR IGNORE INTO counters (key, value) VALUES ('visits', ?)",
        (DEFAULT_VISIT_COUNT,)
    )

    conn.commit()
    conn.close()


def increment_visits():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE counters SET value = value + 1 WHERE key = 'visits'")
    conn.commit()
    cur.execute("SELECT value FROM counters WHERE key = 'visits'")
    value = cur.fetchone()["value"]
    conn.close()
    return value


def get_visit_count():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM counters WHERE key = 'visits'")
    row = cur.fetchone()
    conn.close()
    return row["value"] if row else DEFAULT_VISIT_COUNT


def get_real_leads_count():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM leads")
    row = cur.fetchone()
    conn.close()
    return row["cnt"] if row else 0


def get_display_order_count():
    real_count = get_real_leads_count()
    return max(DEFAULT_ORDER_COUNT, real_count)


@app.route("/")
def index():
    visit_count = increment_visits()
    order_count = get_display_order_count()
    return render_template(
        "klient-no-x5.html",
        visit_count=visit_count,
        order_count=order_count
    )


@app.route("/submit", methods=["POST"])
def submit():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    district = request.form.get("district", "").strip()
    diet = request.form.get("diet", "").strip()

    if not name or not phone:
        return jsonify({"ok": False, "error": "Заполните имя и телефон"}), 400

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO leads (name, phone, district, diet, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name, phone, district, diet, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

    return jsonify({"ok": True})


@app.route("/admin/leads")
def admin_leads():
    token = request.args.get("token", "")
    if token != ADMIN_TOKEN:
        return "Forbidden", 403

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, phone, district, diet, created_at
        FROM leads
        ORDER BY id DESC
    """)
    leads = cur.fetchall()
    conn.close()

    visit_count = get_visit_count()
    order_count = max(DEFAULT_ORDER_COUNT, len(leads))

    rows = []
    for lead in leads:
        rows.append(f"""
            <tr>
                <td>{lead['id']}</td>
                <td>{lead['name']}</td>
                <td>{lead['phone']}</td>
                <td>{lead['district'] or ''}</td>
                <td>{lead['diet'] or ''}</td>
                <td>{lead['created_at']}</td>
            </tr>
        """)

    html = f"""
    <!doctype html>
    <html lang="ru">
    <head>
        <meta charset="utf-8">
        <title>Заявки</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 40px;
                background: #f7f7f7;
                color: #222;
            }}
            .wrap {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                padding: 24px;
                border-radius: 16px;
                box-shadow: 0 8px 30px rgba(0,0,0,.08);
            }}
            h1 {{
                margin-top: 0;
            }}
            .meta {{
                margin-bottom: 20px;
                color: #555;
                display: flex;
                gap: 24px;
                flex-wrap: wrap;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                background: white;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 10px;
                text-align: left;
                font-size: 14px;
                vertical-align: top;
            }}
            th {{
                background: #f0f0f0;
            }}
            tr:nth-child(even) {{
                background: #fafafa;
            }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <h1>Заявки с сайта</h1>
            <div class="meta">
                <div>Всего визитов: <strong>{visit_count}</strong></div>
                <div>Всего заказов: <strong>{order_count}</strong></div>
                <div>Реальных заявок в базе: <strong>{len(leads)}</strong></div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Имя</th>
                        <th>Телефон</th>
                        <th>Район</th>
                        <th>Питание</th>
                        <th>Дата</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows) if rows else '<tr><td colspan="6">Пока нет заявок</td></tr>'}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """
    return html


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
else:
    init_db()