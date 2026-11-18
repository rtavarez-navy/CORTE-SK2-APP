import json
import sqlite3
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from web import weeks
from web.app import app, create_employee, database, setup, today
from web.import_history import import_records, sheet_records
from web.backup import backup


class ProductionTest(unittest.TestCase):
    def setUp(self):
        temp = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(temp) / "app.sqlite3"
        self.enterContext(patch.dict("os.environ", {"CORTE_DB": str(self.path), "CORTE_DEV_HTTP": "1"}))
        setup()
        with database() as db:
            for code, role in (("A", "operator"), ("B", "operator"), ("C", "operator"), ("S", "supervisor")):
                create_employee(db, code, code, role)
            db.executemany("INSERT INTO assignments VALUES (?, ?, ?, ?, ?)",
                           [(today(), 1, 1, 1, "A"), (today(), 1, 1, 2, "B"), (today(), 2, 2, 1, "C")])

    def client(self, employee):
        client = self.enterContext(TestClient(app))
        client.get("/")
        self.post(client, "login", code=employee, password="12345")
        self.post(client, "password", password="prueba-segura", confirm="prueba-segura")
        return client

    def post(self, client, action, status=303, **fields):
        response = client.post("/" + action, data={"csrf": client.cookies["corte_csrf"], **fields},
                               follow_redirects=False)
        self.assertEqual(response.status_code, status, response.text[:450])

    def test_access_duplicate_lifecycle_and_audit(self):
        a, b, c, supervisor = (self.client(code) for code in ("A", "B", "C", "S"))
        location = {"day": today(), "shift": "1", "laser": "1"}
        record = {"order_number": "SO-1234", "line": "AA", "pieces": "25", "comments": "Tela especial"}
        self.post(a, "production", **location, **record, id="a" * 32)
        self.post(a, "production", **location, **record, id="a" * 32)
        self.assertIn("Tela especial", b.get("/").text)
        self.assertNotIn("Tela especial", c.get("/?vista=turno&turno=1&laser=1").text)
        self.assertNotIn("Tela especial", b.get("/?orden=999999").text)
        self.post(c, "production", 403, **location, **record, id="c" * 32)
        self.post(b, "edit-production", 403, **location, **record, record="a" * 32)
        self.post(supervisor, "delete-production", 403, **location, record="a" * 32)
        self.post(b, "production", **location, **(record | {"comments": "Segundo registro"}), id="b" * 32)
        self.post(supervisor, "reprint", order_number="1234", line="aa")
        self.assertIn('data-letter="F"', b.get("/").text)
        self.assertRegex(b.get("/").text, r'data-letter="F"[^>]*>\*</td>')
        self.assertIn("25 piezas confirmadas", b.get("/").text)
        self.post(supervisor, "review", record="b" * 32, decision="approved")
        self.assertIn("50 piezas confirmadas", b.get("/").text)
        self.post(a, "edit-production", **location, **(record | {"pieces": "20"}), record="a" * 32)
        self.assertIn("45 piezas confirmadas", b.get("/").text)
        self.post(a, "delete-production", **location, record="a" * 32)
        self.assertIn("Registros eliminados", a.get("/").text)
        self.assertNotIn("Registros eliminados", b.get("/").text)
        self.assertIn("Eliminación", a.get("/?historial=" + "a" * 32).text)
        self.assertNotIn('id="historial"', b.get("/?historial=" + "a" * 32).text)
        with database() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM production_audit").fetchone()[0], 5)

    def test_weekly_sheet_permissions_totals_and_rollover(self):
        a, b, supervisor = (self.client(code) for code in ("A", "B", "S"))
        day = today()
        live = weeks.week_of(day)
        previous = weeks.week_of((weeks.monday(live) - timedelta(days=1)).isoformat())
        location = {"day": day, "shift": "1", "laser": "1"}
        record = {"order_number": "3986055", "line": "A", "pieces": "20"}
        self.post(a, "production", **location, **record, id="c" * 32)
        page = b.get(f"/?semana={previous}")
        self.assertIn(f'data-week="{live}"', page.text)
        self.assertIn("script-src 'self'", page.headers["content-security-policy"])
        self.assertNotIn("unsafe-inline", page.headers["content-security-policy"])
        self.assertNotIn('id="col-L"', page.text)
        self.assertRegex(page.text, r'<tr class="colleague"[^>]+>.*?aria-readonly="true"')
        self.assertIn("20 piezas confirmadas", page.text)
        self.post(supervisor, "edit-production", **location, **(record | {"pieces": "22"}),
                  record="c" * 32, employee="B", order_line="ALTERADO", dup="100")
        with database() as db:
            self.assertEqual(tuple(db.execute("SELECT employee, order_line, pieces FROM production").fetchone()),
                             ("B", "3986055-A", 22))

        future_day = (weeks.monday(live) + timedelta(days=7)).isoformat()
        folder = self.path.parent / "respaldos"
        with patch.dict("os.environ", {"CORTE_BACKUP_DIR": str(self.path)}), self.assertLogs("web.weeks"):
            weeks.rollover(database, future_day)
        with database() as db:
            cycle = weeks.current(db)
            self.assertEqual(cycle["open_week"], live)
            self.assertIn("Falló el respaldo", cycle["error"])
        self.assertIn("Falló el respaldo", supervisor.get("/?vista=avisos").text)

        with patch.dict("os.environ", {"CORTE_BACKUP_DIR": str(folder)}):
            weeks.rollover(database, future_day)
            weeks.rollover(database, future_day)
        copies = list(folder.glob("*.sqlite3"))
        self.assertEqual(len(copies), 1)
        with sqlite3.connect(copies[0]) as db:
            self.assertEqual(db.execute("SELECT open_week FROM production_cycle").fetchone()[0], live)
        history = supervisor.get("/?vista=historia").text
        self.assertIn("3986055-A", history)
        self.assertNotIn("edit-production", history)
        self.post(supervisor, "edit-production", 403, **location, **record, record="c" * 32)

    def test_supervisor_paste_is_atomic(self):
        supervisor, operator = (self.client(code) for code in ("S", "A"))
        payload = {"day": today(), "shift": "1", "laser": "1", "employee": "A"}
        first = {"id": "d" * 32, "order_number": "111", "line": "A", "pieces": "20"}
        second = {"id": "e" * 32, "order_number": "222", "line": "A", "pieces": "bad"}
        self.post(operator, "production", 403, **payload, batch=json.dumps([first]))
        self.post(supervisor, "production", 400, **payload, batch=json.dumps([first, second]))
        with database() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM production").fetchone()[0], 0)
        batch = json.dumps([first, second | {"pieces": "21"}])
        self.post(supervisor, "production", **payload, batch=batch)
        self.post(supervisor, "production", **payload, batch=batch)
        with database() as db:
            self.assertEqual([row[0] for row in db.execute("SELECT order_number FROM production ORDER BY rowid")],
                             ["111", "222"])

    def test_history_csv_keeps_duplicates_and_is_idempotent(self):
        live = weeks.week_of(today())
        previous = weeks.monday(live) - timedelta(days=1)
        path = self.path.parent / "Historia.csv"
        path.write_text(f"FECHA,#ORDEN,LINEA,CANT,COMENT,LASER,Resumen\n"
                        f"{previous:%d/%m/%Y},SO-004,A,12,,Laser 10 T2\n"
                        f"{previous:%d/%m/%Y},SO-004,A,13,,Laser 10 T2\n"
                        " ,,,,,,Totales\n", encoding="utf-8")
        rows, errors = sheet_records(path, "historia")
        self.assertFalse(errors)
        with database() as db:
            self.assertEqual(import_records(db, rows), 2)
            self.assertEqual(import_records(db, rows), 0)
            saved = db.execute("SELECT laser, shift, order_line, SUM(pieces) FROM production").fetchone()
            self.assertEqual(tuple(saved), (10, 2, "004-A", 25))


    def test_migration_and_backup(self):
        with database() as db:
            for name in ("order_number", "line", "comments", "sku", "order_line", "deleted_at"):
                db.execute("DROP INDEX IF EXISTS production_day")
                db.execute("DROP INDEX IF EXISTS production_week_laser")
                db.execute("DROP INDEX IF EXISTS production_key")
                db.execute(f"ALTER TABLE production DROP COLUMN {name}")
            db.execute("""
                INSERT INTO production (id, day, shift, laser, employee, reference, pieces, recorded_by)
                VALUES ('legacy', ?, 1, 1, 'A', 'SO-1234 / AA', 42, 'A')
            """, (today(),))
        destination = self.path.with_suffix(".backup")
        backup(self.path, destination)
        with sqlite3.connect(destination) as db:
            self.assertEqual(db.execute("SELECT pieces FROM production").fetchone()[0], 42)
        setup()
        setup()
        with database() as db:
            row = db.execute("SELECT line, order_line, pieces, review FROM production").fetchone()
            self.assertEqual(tuple(row), ("AA", "1234-AA", 42, "approved"))


if __name__ == "__main__":
    unittest.main()
