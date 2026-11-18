import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from web.app import app, create_employee, database, setup, today
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
        self.assertIn("<td>*</td>", b.get("/").text)
        self.assertIn("25 piezas confirmadas", b.get("/").text)
        self.post(supervisor, "review", record="b" * 32, decision="approved")
        self.assertIn("50 piezas confirmadas", b.get("/").text)
        self.post(a, "edit-production", **location, **(record | {"pieces": "20"}), record="a" * 32)
        self.assertIn("45 piezas confirmadas", b.get("/").text)
        self.post(a, "delete-production", **location, record="a" * 32)
        self.assertIn("Registros eliminados", a.get("/").text)
        self.assertNotIn("Registros eliminados", b.get("/").text)
        self.assertIn("Eliminación", a.get("/?historial=" + "a" * 32).text)
        self.assertNotIn("Historial de cambios", b.get("/?historial=" + "a" * 32).text)
        with database() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM production_audit").fetchone()[0], 5)

    def test_migration_and_backup(self):
        with database() as db:
            for name in ("order_number", "line", "comments", "sku", "order_line", "deleted_at"):
                db.execute("DROP INDEX IF EXISTS production_day")
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
            self.assertEqual(tuple(row), ("AA", "1234AA", 42, "approved"))


if __name__ == "__main__":
    unittest.main()
