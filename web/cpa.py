"""Read-only order lookup in the CPA database maintained by URA."""
from contextlib import closing
import logging
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote

logger = logging.getLogger(__name__)
FIELDS = {
    "ORDER": ("Order", "SO #", "Order Number", "SalesId"),
    "SET": ("Set",),
    "QTY": ("Qty", "Quantity", "Pieces", "PCS"),
    "STATUS": ("Line Status",),
    "FACTORY": ("Factory",),
}


class CpaUnavailable(Exception):
    pass


def normalized(column):
    return re.sub(r"[^a-z0-9]", "", column.casefold())


def sql_identifier(column):
    return '"' + column.replace('"', '""') + '"'


def resolve_columns(db):
    available = [row[1] for row in db.execute("PRAGMA table_info(cpa_lines)")]
    selected = {}
    for field, aliases in FIELDS.items():
        override = os.environ.get(f"CPA_COLUMN_{field}")
        if override:
            matches = [name for name in available if name == override]
        else:
            acceptable = {normalized(alias) for alias in aliases}
            matches = [name for name in available if normalized(name) in acceptable]
        if len(matches) != 1:
            logger.warning("CPA column %s requires configuration (matches: %s)", field, matches)
            raise CpaUnavailable("La estructura de CPA requiere configurar las columnas en el servidor.")
        selected[field] = sql_identifier(matches[0])
    return selected


def lookup(order):
    raw_path = os.environ.get("CPA_DB")
    if not raw_path:
        raise CpaUnavailable("La consulta CPA aún no está configurada en este servidor.")
    if not re.fullmatch(r"(?:SO-)?[0-9]{1,24}", order, re.IGNORECASE):
        raise ValueError("Escribe un número de orden, por ejemplo SO-1234567.")
    number = order.upper().removeprefix("SO-")
    factory = os.environ.get("CPA_FACTORY", "JuiceSakira2").strip()
    if not factory:
        raise CpaUnavailable("La fábrica de CPA debe estar configurada en el servidor.")
    try:
        path = Path(raw_path).absolute()
        location = path.as_posix()
        # A Windows UNC path needs an empty URI authority and a double-slash path.
        uri = "file://" + quote(location, safe="/:") if location.startswith("//") else path.as_uri()
        with closing(sqlite3.connect(uri + "?mode=ro", uri=True, timeout=2)) as db:
            db.execute("PRAGMA query_only = ON")
            cols = resolve_columns(db)
            rows = db.execute(f"""
                SELECT {cols['ORDER']}, {cols['SET']}, {cols['QTY']}, {cols['STATUS']}
                FROM "cpa_lines"
                WHERE {cols['ORDER']} COLLATE NOCASE IN (?, ?)
                  AND {cols['FACTORY']} COLLATE NOCASE = ?
                ORDER BY {cols['SET']}
                LIMIT 101
            """, (number, f"SO-{number}", factory)).fetchall()
    except (OSError, sqlite3.Error):
        logger.exception("Unable to read CPA database")
        raise CpaUnavailable("CPA no está disponible en este momento. Intenta de nuevo.") from None
    return rows[:100], len(rows) > 100
