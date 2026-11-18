"""Import a CSV exported from the Historia tab of Corte Sakira 2."""
import argparse
import csv
from hashlib import sha256
import os
from pathlib import Path
import re

from web import production as ledger, weeks
from web.app import database, setup
from web.backup import backup

HISTORICAL_EMPLOYEE = "@HISTORIA"
HEADER = ("FECHA", "#ORDEN", "LINEA", "CANT", "COMENT", "LASER")


def sheet_records(path, source):
    failures = []
    records = []
    csv.field_size_limit(16 * 1024 * 1024)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = tuple(item.strip().upper() for item in next(reader, [])[:6])
        if header != HEADER:
            raise ValueError("El CSV debe comenzar con FECHA, #ORDEN, LINEA, CANT, COMENT y LASER.")
        for number, row in enumerate(reader, 2):
            day, order, line, pieces, comments, station = (row + [""] * 6)[:6]
            if not any(value.strip() for value in (order, pieces, station)):
                continue
            try:
                machine = re.fullmatch(r"L[aá]ser\s+(1[01]|[1-9])\s+T([12])", station.strip(), re.I)
                if not machine:
                    raise ValueError("Láser o turno inválido")
                laser, shift = map(int, machine.groups())
                production_day = weeks.parse_day(day)
                order, line, qty, comments, _, key = ledger.values({
                    "order_number": order, "line": line, "pieces": pieces.strip(), "comments": comments,
                })
                record_id = sha256(f"{source}:{number}".encode()).hexdigest()[:32]
                records.append((number, record_id, production_day, shift, laser, f"{order} / {line}",
                                qty, order, line, comments, key, weeks.week_of(production_day)))
            except ValueError as exc:
                failures.append((number, str(exc)))
    return records, failures


def import_records(db, records):
    open_week = weeks.current(db)["open_week"]
    db.execute("""INSERT OR IGNORE INTO employees
        (code, name, role, password, pending, active) VALUES (?, 'Historia importada', 'operator', '', 1, 0)
        """, (HISTORICAL_EMPLOYEE,))
    existing = {tuple(row) for row in db.execute(
        """SELECT id, day, shift, laser, reference, pieces, order_number, line, comments, order_line, week
           FROM production WHERE recorded_by=?""", (HISTORICAL_EMPLOYEE,))}
    imported_ids = {row[0] for row in existing}
    pending_inserts = []
    for number, *row in records:
        if row[-1] >= open_week:
            raise ValueError(f"Fila {number}: la fecha pertenece a una semana abierta o futura.")
        if row[0] in imported_ids:
            if tuple(row) not in existing:
                raise ValueError(f"Fila {number}: el origen difiere de una importación anterior.")
        else:
            pending_inserts.append((*row, HISTORICAL_EMPLOYEE, HISTORICAL_EMPLOYEE))
    db.executemany("""INSERT INTO production
        (id, day, shift, laser, reference, pieces, order_number, line, comments, order_line, week,
         employee, recorded_by, review) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved')
        """, pending_inserts)
    return len(pending_inserts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--source", default="corte-sakira-2-historia", help="identificador estable del CSV de origen")
    parser.add_argument("--backup", type=Path, help="ruta nueva de respaldo SQLite para aplicar la importación")
    parser.add_argument("--skip-invalid", action="store_true", help="omitir explícitamente las filas inválidas")
    args = parser.parse_args()
    try:
        rows, rejected = sheet_records(args.csv, args.source)
        print(f"{len(rows):,} filas válidas. {len(rejected):,} filas con errores.")
        for index, reason in rejected[:20]:
            print(f"Fila {index}: {reason}")
        if rejected and not args.skip_invalid:
            parser.exit(1, "Corrige el CSV antes de cargarlo.\n")
        if not args.backup:
            return
        source = Path(os.environ.get("CORTE_DB", "corte-sk2.sqlite3"))
        if not source.is_file():
            raise ValueError("CORTE_DB debe apuntar a la base existente del servidor.")
        backup(source, args.backup)
        setup()
        with database() as db:
            db.execute("BEGIN IMMEDIATE")
            print(f"{import_records(db, rows):,} filas importadas.")
    except (OSError, ValueError, csv.Error) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
