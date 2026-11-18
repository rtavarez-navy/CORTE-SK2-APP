"""ISO production weeks and backup-gated rollover."""
from datetime import date, datetime, timedelta
import logging
import os
from pathlib import Path
import sqlite3

from web.backup import backup

LOGGER = logging.getLogger(__name__)


def week_of(day):
    year, week, _ = date.fromisoformat(day).isocalendar()
    return f"{year:04d}-S{week:02d}"


def monday(week):
    year, number = week.split("-S")
    return date.fromisocalendar(int(year), int(number), 1)


def parse_day(value):
    value = value.strip()
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        pass
    try:
        return datetime.strptime(value, "%d/%m/%Y").date().isoformat()
    except ValueError:
        raise ValueError("Usa una fecha válida (DD/MM/AAAA).") from None


def migrate(db, day):
    columns = {column["name"] for column in db.execute("PRAGMA table_info(production)")}
    if "week" not in columns:
        db.execute("ALTER TABLE production ADD COLUMN week TEXT NOT NULL DEFAULT ''")
    db.create_function("production_week", 1, week_of)
    db.execute("UPDATE production SET week = production_week(day) WHERE week = ''")
    db.execute("""CREATE INDEX IF NOT EXISTS production_week_laser
        ON production(week, shift, laser, day) WHERE deleted_at IS NULL""")
    db.execute("""CREATE TABLE IF NOT EXISTS production_cycle (
        id INTEGER PRIMARY KEY CHECK (id = 1), open_week TEXT NOT NULL, error TEXT
    )""")
    db.execute("INSERT OR IGNORE INTO production_cycle VALUES (1, ?, NULL)", (week_of(day),))


def current(db):
    return db.execute("SELECT * FROM production_cycle WHERE id = 1").fetchone()


def rollover(database, day):
    target = week_of(day)
    with database() as db:
        if current(db)["open_week"] >= target:
            return
        db.execute("BEGIN IMMEDIATE")
        previous = current(db)["open_week"]
        if previous >= target:
            return
        try:
            source = Path(os.environ.get("CORTE_DB", "corte-sk2.sqlite3"))
            folder = Path(os.environ.get("CORTE_BACKUP_DIR", str(source.parent / "respaldos")))
            folder.mkdir(parents=True, exist_ok=True)
            name = f"{source.stem}-{previous}-{datetime.now():%Y%m%d%H%M%S%f}.sqlite3"
            backup(source, folder / name)
        except (OSError, RuntimeError, sqlite3.Error):
            LOGGER.exception("No se pudo respaldar el cierre de %s", previous)
            db.execute("UPDATE production_cycle SET error = ? WHERE id = 1",
                       (f"No se cerró {previous}. Falló el respaldo y la hoja anterior sigue disponible.",))
            return
        db.execute("UPDATE production_cycle SET open_week = ?, error = NULL WHERE id = 1", (target,))


def label(week):
    start = monday(week)
    end = start + timedelta(days=6)
    return f"{week} · {start:%d/%m/%Y} al {end:%d/%m/%Y}"
