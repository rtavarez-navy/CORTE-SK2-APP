"""Production schema, duplicate rules and audit trail."""
from datetime import datetime, timezone
import json
import re


def reference_key(order, line):
    return order.upper().removeprefix("SO-") + line.upper()


def migrate(db):
    columns = {row["name"] for row in db.execute("PRAGMA table_info(production)")}
    if "order_number" not in columns:
        for name in ("order_number", "line", "comments", "sku", "order_line"):
            db.execute(f"ALTER TABLE production ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
        db.execute("ALTER TABLE production ADD COLUMN deleted_at TEXT")
        rows = db.execute("SELECT id, reference FROM production").fetchall()
        for row in rows:
            ref = row["reference"].strip()
            match = re.fullmatch(r"((?:SO-)?[0-9]+)[ /-]*([A-Z]+)", ref, re.IGNORECASE)
            order, line = match.groups() if match else (ref, "")
            db.execute("""
                UPDATE production SET order_number = ?, line = ?, order_line = ? WHERE id = ?
            """, (order, line, reference_key(order, line), row["id"]))
    db.execute("""
        CREATE TABLE IF NOT EXISTS production_audit (
            sequence INTEGER PRIMARY KEY, record_id TEXT NOT NULL REFERENCES production(id),
            actor TEXT NOT NULL REFERENCES employees(code), event TEXT NOT NULL,
            occurred_at TEXT NOT NULL, previous TEXT, current TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS valid_reprints (
            order_line TEXT PRIMARY KEY, order_number TEXT NOT NULL, line TEXT NOT NULL
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS production_key ON production(order_line, shift, laser) WHERE deleted_at IS NULL")
    db.execute("CREATE INDEX IF NOT EXISTS production_day ON production(day, shift, laser) WHERE deleted_at IS NULL")
    db.execute("CREATE INDEX IF NOT EXISTS audit_record ON production_audit(record_id, sequence)")


def get_record(db, key):
    return db.execute("SELECT * FROM production WHERE id = ?", (key,)).fetchone()


def audit(db, key, actor, event, previous=None):
    db.execute("""
        INSERT INTO production_audit (record_id, actor, event, occurred_at, previous, current)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (key, actor, event, datetime.now(timezone.utc).isoformat(timespec="seconds"),
          json.dumps(dict(previous), ensure_ascii=False) if previous else None,
          json.dumps(dict(get_record(db, key)), ensure_ascii=False)))


def order_fields(data):
    order = data.get("order_number", "").strip().upper().removeprefix("SO-")
    line = data.get("line", "").strip().upper()
    if not re.fullmatch(r"[0-9]{1,24}", order) or not re.fullmatch(r"[A-Z0-9]{1,12}", line):
        raise ValueError("Escribe la orden (con o sin SO-) y la línea en campos separados.")
    return order, line


def values(data):
    order, line = order_fields(data)
    pieces = data.get("pieces", "")
    comments = data.get("comments", "").strip()
    sku = data.get("sku", "").strip()
    if not re.fullmatch(r"[0-9]{1,6}", pieces) or not 1 <= int(pieces) <= 100000:
        raise ValueError("Escribe una cantidad entre 1 y 100,000 piezas.")
    if len(comments) > 300 or len(sku) > 60:
        raise ValueError("El comentario admite 300 caracteres y el SKU admite 60.")
    return order, line, int(pieces), comments, sku, reference_key(order, line)


def review_status(db, key, record_id):
    duplicate = db.execute("""
        SELECT 1 FROM production WHERE order_line = ? AND id != ?
        AND deleted_at IS NULL AND review != 'rejected' LIMIT 1
    """, (key, record_id)).fetchone()
    return "pending" if duplicate else "approved"


def report_counts(db, rows, shift, laser):
    counts = {}
    keys = sorted({row["order_line"] for row in rows})
    for offset in range(0, len(keys), 500):
        chunk = keys[offset:offset + 500]
        placeholders = ",".join("?" for _ in chunk)
        query = f"""
            SELECT p.order_line, SUM(p.review != 'rejected') AS total,
                   SUM(p.shift = ? AND p.laser = ? AND p.review != 'rejected') AS local,
                   r.order_line IS NOT NULL AS reprint
            FROM production p LEFT JOIN valid_reprints r ON r.order_line = p.order_line
            WHERE p.deleted_at IS NULL
              AND p.order_line IN ({placeholders})
            GROUP BY p.order_line
        """
        counts.update({row["order_line"]: row for row in db.execute(query, (shift, laser, *chunk))})
    return counts
