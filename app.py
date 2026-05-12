from flask import Flask, render_template, request, redirect, url_for, Response
from datetime import datetime
from pathlib import Path
import sqlite3
import html
import os

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "data.db")))
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "my-super-secret-123")

INITIAL_VISITS = 70812
INITIAL_ORDERS = 2213

app = Flask(__name__, template_folder=str(TEMPLATES_DIR))


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                form_type TEXT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                district TEXT,
                diet TEXT
            )
        """)
        conn.commit()


def get_orders_count():
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM leads").fetchone()
        return INITIAL_ORDERS + (row["cnt"] if row else 0)


def esc(value):
    return html.escape(str(value if value is not None else ""))


init_db()


@app.route("/", methods=["GET"])
def index():
    return render_template(
        "klient-no-x5.html",
        visit_count=INITIAL_VISITS,
        order_count=get_orders_count(),
    )


@app.route("/submit", methods=["POST"])
def submit():
    form_type = (request.form.get("form_type") or "unknown").strip()
    name = (request.form.get("name") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    district = (request.form.get("district") or "").strip()
    diet = (request.form.get("diet") or "").strip()

    if not name or not phone:
        return redirect(url_for("index"))

    with get_conn() as conn:
        conn.execute("""
            INSERT INTO leads (created_at, form_type, name, phone, district, diet)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(timespec="seconds"),
            form_type,
            name,
            phone,
            district,
            diet,
        ))
        conn.commit()

    return redirect(url_for("index"))


@app.route("/admin/leads", methods=["GET"])
def admin_leads():
    token = request.args.get("token", "")
    if token != ADMIN_TOKEN:
        return Response("Forbidden", status=403)

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT id, created_at, form_type, name, phone, district, diet
            FROM leads
            ORDER BY id DESC
        """).fetchall()

    rows_html = "".join(
        f"""
        <tr>
          <td>{esc(row["id"])}</td>
          <td>{esc(row["created_at"])}</td>
          <td>{esc(row["form_type"])}</td>
          <td>{esc(row["name"])}</td>
          <td>{esc(row["phone"])}</td>
          <td>{esc(row["district"])}</td>
          <td>{esc(row["diet"])}</td>
        </tr>
        """
        for row in rows
    )

    page = f"""
    <!doctype html>
    <html lang="ru">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Заявки</title>
      <style>
        body {{
          margin: 0;
          font-family: Arial, sans-serif;
          background: #f6f6f4;
          color: #1a1a18;
        }}
        .wrap {{
          max-width: 1280px;
          margin: 0 auto;
          padding: 24px;
        }}
        .top {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 16px;
          flex-wrap: wrap;
          margin-bottom: 20px;
        }}
        .chip {{
          background: #fff;
          border: 1px solid rgba(0, 0, 0, .08);
          border-radius: 12px;
          padding: 10px 14px;
        }}
        .table-wrap {{
          overflow: auto;
          border: 1px solid rgba(0, 0, 0, .08);
          border-radius: 16px;
          background: #fff;
        }}
        table {{
          width: 100%;
          border-collapse: collapse;
        }}
        th, td {{
          padding: 12px;
          border-bottom: 1px solid rgba(0, 0, 0, .08);
          text-align: left;
          vertical-align: top;
          font-size: 14px;
          white-space: nowrap;
        }}
        th {{
          background: #f0eee9;
          position: sticky;
          top: 0;
        }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="top">
          <div>
            <h1 style="margin:0 0 6px;">Все заявки</h1>
            <div style="color:#6b6a66;">База: {esc(str(DB_PATH))}</div>
          </div>
          <div class="chip">Записей в БД: <strong>{len(rows)}</strong></div>
        </div>

        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Дата</th>
                <th>Форма</th>
                <th>Имя</th>
                <th>Телефон</th>
                <th>Район</th>
                <th>Тип питания</th>
              </tr>
            </thead>
            <tbody>
              {rows_html or '<tr><td colspan="7">Записей пока нет</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>
    </body>
    </html>
    """
    return Response(page, mimetype="text/html; charset=utf-8")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)