"""CORTE SK2, servidor web de planta."""
import argparse
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from hashlib import pbkdf2_hmac, sha256
from hmac import compare_digest
from html import escape
import os
from pathlib import Path
import re
from secrets import token_hex, token_urlsafe
import sqlite3
from time import time
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

INITIAL_PASSWORD = "12345"
ROLES = {"developer": "Desarrollador", "supervisor": "Supervisor", "operator": "Operador"}
ZONE = ZoneInfo("America/Santo_Domingo")
SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    code TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
    password TEXT NOT NULL, pending INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY, employee TEXT NOT NULL REFERENCES employees(code),
    expires INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS assignments (
    day TEXT NOT NULL, shift INTEGER NOT NULL CHECK (shift IN (1, 2)),
    laser INTEGER NOT NULL CHECK (laser BETWEEN 1 AND 11),
    employee TEXT NOT NULL REFERENCES employees(code),
    PRIMARY KEY (day, shift, laser), UNIQUE (day, shift, employee)
);
CREATE TABLE IF NOT EXISTS attempts (
    key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS production (
    id TEXT PRIMARY KEY, day TEXT NOT NULL, shift INTEGER NOT NULL,
    laser INTEGER NOT NULL, employee TEXT NOT NULL REFERENCES employees(code),
    reference TEXT NOT NULL, pieces INTEGER NOT NULL CHECK (pieces > 0),
    recorded_by TEXT NOT NULL REFERENCES employees(code)
);
"""


def today():
    return datetime.now(ZONE).date().isoformat()


@contextmanager
def database():
    path = os.environ.get("CORTE_DB", "corte-sk2.sqlite3")
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys = ON")
        with db:
            yield db
    finally:
        db.close()


def password_hash(password, salt=None):
    salt = salt or token_hex(16)
    result = pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600_000)
    return salt + ":" + result.hex()


def digest(token):
    return sha256(token.encode()).hexdigest()


def create_employee(db, code, name, role):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,24}", code) or not 1 <= len(name) <= 80 or role not in ROLES:
        raise ValueError("Revisa el código, el nombre y el rol.")
    db.execute("INSERT INTO employees (code, name, role, password, pending) VALUES (?, ?, ?, ?, 1)",
               (code.upper(), name, role, password_hash(INITIAL_PASSWORD)))


def setup():
    with database() as db:
        db.executescript(SCHEMA)
        db.execute("BEGIN IMMEDIATE")
        columns = {row["name"] for row in db.execute("PRAGMA table_info(employees)")}
        if "active" not in columns:
            db.execute("ALTER TABLE employees ADD COLUMN active INTEGER NOT NULL DEFAULT 1")


@asynccontextmanager
async def lifespan(_app):
    await run_in_threadpool(setup)
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'self'; form-action 'self'; "
        "frame-ancestors 'none'; base-uri 'none'"
    )
    return response


def cookie(response, name, value):
    response.set_cookie(name, value, httponly=True, samesite="strict",
                        secure=os.environ.get("CORTE_DEV_HTTP") != "1", max_age=28800)


def employee(db, request):
    return db.execute("""
        SELECT e.* FROM sessions s JOIN employees e ON s.employee = e.code
        WHERE s.token = ? AND s.expires > ? AND e.active = 1
    """, (digest(request.cookies.get("corte_session", "")), int(time()))).fetchone()


def hidden(name, value):
    return f'<input type="hidden" name="{name}" value="{escape(str(value))}">'


def form(action, csrf, fields):
    return f'<form method="post" action="/{action}">{hidden("csrf", csrf)}{fields}</form>'


def page(title, content, error="", status=200, wide=False):
    alert = f'<p role="alert" class="alert">{escape(error)}</p>' if error else ""
    return HTMLResponse(f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} · Corte SK2</title><link rel="stylesheet" href="/style.css">
</head><body><main class="{'dashboard' if wide else 'login'}">
<header><a href="/" class="brand"><span class="mark" aria-hidden="true">✳</span> CORTE <strong>SK2</strong></a></header>
{alert}{content}</main></body></html>""", status)


@app.get("/style.css")
def stylesheet():
    return FileResponse(Path(__file__).with_name("style.css"), media_type="text/css")


def render(request, error="", status=200):
    csrf = request.cookies.get("corte_csrf") or token_urlsafe(32)
    with database() as db:
        user = employee(db, request)
        if not user:
            contents = '<h1>Iniciar sesión</h1>' + form("login", csrf, """
                <label>Código de empleado<input name="code" autocomplete="username" maxlength="24" required autofocus></label>
                <label>Contraseña<input type="password" name="password" autocomplete="current-password" maxlength="128" required></label>
                <button>Entrar</button>""")
            contents += """<details class="recovery"><summary>Olvidé mi contraseña</summary>
                <p>Solicita el restablecimiento a tu supervisor e indícale tu código de empleado.
                Si eres supervisor, solicítalo al desarrollador. Cuando te confirmen el cambio,
                entra con la clave temporal y elige una nueva.</p></details>"""
            response = page("Inicio de sesión", contents, error, status)
        elif user["pending"]:
            contents = '<h1>Cambia tu contraseña</h1><p>Usa al menos 8 caracteres para continuar.</p>' + form("password", csrf, """
                <label>Nueva contraseña<input type="password" name="password" autocomplete="new-password" minlength="8" maxlength="128" required></label>
                <label>Confirmar contraseña<input type="password" name="confirm" autocomplete="new-password" minlength="8" maxlength="128" required></label>
                <button>Guardar y continuar</button>""") + form("logout", csrf, '<button class="quiet">Cerrar sesión</button>')
            response = page("Primer acceso", contents, error, status)
        else:
            response = dashboard(db, request, user, csrf, error, status)
    if not request.cookies.get("corte_csrf"):
        cookie(response, "corte_csrf", csrf)
    return response


def dashboard(db, request, user, csrf, error, status):
    day = today()
    shift = 2 if request.query_params.get("turno") == "2" else 1
    operator = user["role"] == "operator"
    filters = (day, user["code"]) if operator else (day,)
    by_employee = " AND employee = ?" if operator else ""
    slots = db.execute("SELECT * FROM assignments WHERE day = ?" + by_employee, filters).fetchall()
    totals = db.execute("""
        SELECT shift, laser, sum(pieces) AS pieces FROM production WHERE day = ?
    """ + by_employee + " GROUP BY shift, laser", filters).fetchall()
    amounts = {(r["shift"], r["laser"]): r["pieces"] for r in totals}
    report_rows = db.execute("""
        SELECT laser, reference, pieces, employee FROM production WHERE day = ? AND shift = ?
    """ + by_employee + " ORDER BY rowid", (day, shift, *filters[1:])).fetchall()
    assigned = {(r["shift"], r["laser"]): r["employee"] for r in slots}
    staff = {}
    if not operator:
        staff = {r["code"]: r["name"] for r in db.execute(
            "SELECT code, name FROM employees WHERE role = 'operator' AND active = 1 ORDER BY name, code")}
    summary = "".join(
        f'<tr><th scope="row">Turno {turn}</th><td>{sum(key[0] == turn for key in assigned)}'
        f'{" / 11" if not operator else ""}</td><td>{sum(value for key, value in amounts.items() if key[0] == turn):,}</td></tr>'
        for turn in (1, 2)
    )
    cards = []
    for laser in range(1, 12):
        code = assigned.get((shift, laser))
        if operator and not code:
            continue
        fields = hidden("shift", shift) + hidden("laser", laser) + hidden("day", day)
        entry_form = ""
        entry_row = ""
        if operator or (code and user["role"] == "developer"):
            form_id = f"capture-{laser}"
            entry_form = f'<form id="{form_id}" method="post" action="/production">' + (
                fields + hidden("employee", code) + hidden("id", token_hex(16)) + hidden("csrf", csrf)
            ) + '</form>'
            entry_row = f"""<tr><td>+</td><td><input form="{form_id}" name="reference"
                aria-label="Orden o línea, láser {laser}" maxlength="80" required></td>
                <td>{escape(code)}</td><td><input form="{form_id}" name="pieces" type="number"
                aria-label="Piezas, láser {laser}" min="1" max="100000" required></td>
                <td><button form="{form_id}">Registrar</button></td></tr>"""
        rows = "".join(
            f'<tr><td>{index}</td><td>{escape(row["reference"])}</td><td>{escape(row["employee"])}</td>'
            f'<td>{row["pieces"]:,}</td><td></td></tr>'
            for index, row in enumerate((row for row in report_rows if row["laser"] == laser), 1)
        )
        if not rows and not entry_row:
            rows = '<tr><td colspan="5">Sin registros para este turno.</td></tr>'
        editor = ""
        if not operator:
            options = "".join(
                f'<option value="{escape(key)}" {"selected" if key == code else ""}>{escape(name)} · {escape(key)}</option>'
                for key, name in staff.items())
            fields += f'<label>Operador<select name="employee"><option value="">Sin asignar</option>{options}</select></label><button>Guardar asignación</button>'
            editor = form("assign", csrf, fields)
        cards.append(f"""<article><details {"open" if operator or request.query_params.get("laser") == str(laser) else ""}>
            <summary><strong>Láser {laser:02}</strong> <span>{amounts.get((shift, laser), 0):,} piezas</span></summary>
            {editor}{entry_form}<div class="sheet"><table aria-label="Reporte del láser {laser}">
            <thead><tr><th>#</th><th>Orden / línea</th><th>Operador</th><th>Piezas</th><th>Acción</th></tr></thead>
            <tbody>{rows}{entry_row}</tbody></table></div></details></article>""")
    grid = "".join(cards) or '<p>Sin máquina asignada para este turno.</p>'
    tabs = "".join(f'<a href="/?turno={turn}" {"aria-current=page" if turn == shift else ""}>Turno {turn}</a>' for turn in (1, 2))
    account = "" if operator else accounts_panel(db, user, csrf)
    contents = f"""<div class="toolbar"><div><h1>Producción de corte</h1>
        <p>{escape(user['name'])} · {ROLES[user['role']]} · {day}</p></div>
        {form('logout', csrf, '<button class="quiet">Cerrar sesión</button>')}</div>
        <section><h2>Resumen del día</h2><table><thead><tr><th>Turno</th>
        <th>Láseres asignados</th><th>Piezas registradas</th></tr></thead><tbody>{summary}</tbody></table></section>
        <nav aria-label="Turno">{tabs}</nav><h2>{'Mi máquina' if operator else 'Láseres'}</h2>
        <div class="grid">{grid}</div>{account}"""
    return page("Producción de corte", contents, error, status, wide=True)


def accounts_panel(db, user, csrf):
    roles = ("operator", "supervisor") if user["role"] == "developer" else ("operator",)
    options = "".join(f'<option value="{role}">{ROLES[role]}</option>' for role in roles)
    creation = form("employees", csrf, f"""
        <label>Código de empleado<input name="code" maxlength="24" required></label>
        <label>Nombre<input name="name" maxlength="80" required></label>
        <label>Rol<select name="role">{options}</select></label><button>Crear cuenta</button>""")
    rows = []
    for entry in db.execute("SELECT code, name, role FROM employees WHERE active = 1 ORDER BY name, code"):
        if entry["role"] not in roles:
            continue
        code = hidden("code", entry["code"])
        reset = form("reset-account", csrf, code + '<button class="quiet">Restablecer a 12345</button>')
        remove = form("remove-account", csrf, code + '<button class="danger">Confirmar baja</button>')
        rows.append(f"""<tr><td>{escape(entry["code"])}</td><td>{escape(entry["name"])}</td>
            <td>{ROLES[entry["role"]]}</td><td>{reset}<details><summary>Dar de baja</summary>
            <p>Revoca el acceso y libera sus asignaciones activas.</p>{remove}</details></td></tr>""")
    listing = "".join(rows) or '<tr><td colspan="4">Sin cuentas para gestionar.</td></tr>'
    return f"""<section id="cuentas"><h2>Cuentas</h2>{creation}<div class="sheet"><table>
        <thead><tr><th>Código</th><th>Nombre</th><th>Rol</th><th>Acciones</th></tr></thead>
        <tbody>{listing}</tbody></table></div></section>"""


def manage_account(db, user, action, data):
    roles = ("operator", "supervisor") if user["role"] == "developer" else ("operator",)
    if action == "employees":
        role = data.get("role")
        if role not in roles:
            raise HTTPException(403)
        create_employee(db, data.get("code", "").strip(), data.get("name", "").strip(), role)
        return
    code = data.get("code", "").strip().upper()
    target = db.execute("SELECT role FROM employees WHERE code = ? AND active = 1", (code,)).fetchone()
    if not target or target["role"] not in roles:
        raise HTTPException(403)
    db.execute("DELETE FROM sessions WHERE employee = ?", (code,))
    if action == "reset-account":
        db.execute("UPDATE employees SET password = ?, pending = 1 WHERE code = ?",
                   (password_hash(INITIAL_PASSWORD), code))
        db.execute("DELETE FROM attempts WHERE key = ?", (f"code:{code}",))
    else:
        db.execute("UPDATE employees SET active = 0 WHERE code = ?", (code,))
        db.execute("DELETE FROM assignments WHERE employee = ? AND day >= ?", (code, today()))


@app.get("/")
def index(request: Request):
    return render(request)


async def fields(request):
    if request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
        raise HTTPException(415)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 8192:
            raise HTTPException(413)
    try:
        parsed = parse_qs(body.decode(), keep_blank_values=True, max_num_fields=12)
    except ValueError:
        raise HTTPException(400) from None
    result = {key: values[-1] for key, values in parsed.items()}
    csrf = request.cookies.get("corte_csrf", "")
    if not csrf or not compare_digest(csrf.encode(), result.get("csrf", "").encode()):
        raise HTTPException(403)
    return result


def login(db, request, data):
    db.execute("BEGIN IMMEDIATE")
    now = int(time())
    db.execute("DELETE FROM attempts WHERE expires <= ?", (now,))
    db.execute("DELETE FROM sessions WHERE expires <= ?", (now,))
    code = data.get("code", "").strip().upper()
    ip = request.client.host if request.client else "local"
    limits = ((f"code:{code}", 8), (f"ip:{ip}", 60))
    for key, limit in limits:
        row = db.execute("SELECT count FROM attempts WHERE key = ?", (key,)).fetchone()
        if row and row["count"] >= limit:
            return None, "Demasiados intentos. Intenta de nuevo en unos minutos.", 429
    user = db.execute("SELECT * FROM employees WHERE code = ? AND active = 1", (code,)).fetchone()
    stored = user["password"] if user else "0" * 32 + ":" + "0" * 64
    password = data.get("password", "")
    matches = compare_digest(stored, password_hash(password[:128], stored.split(":")[0]))
    if not user or len(password) > 128 or not matches:
        db.executemany("""
            INSERT INTO attempts VALUES (?, 1, ?)
            ON CONFLICT(key) DO UPDATE SET count = count + 1
        """, [(key, now + 600) for key, _ in limits])
        return None, "Código o contraseña incorrectos.", 401
    db.execute("DELETE FROM attempts WHERE key = ?", (f"code:{code}",))
    token = token_urlsafe(32)
    db.execute("DELETE FROM sessions WHERE token = ?",
               (digest(request.cookies.get("corte_session", "")),))
    db.execute("INSERT INTO sessions VALUES (?, ?, ?)", (digest(token), code, now + 28800))
    return token, "", 200


def slot(data):
    if data.get("day") != today():
        raise ValueError("Cambió la fecha de operación. Vuelve a seleccionar el turno.")
    try:
        shift, laser = int(data.get("shift", "")), int(data.get("laser", ""))
    except ValueError:
        raise ValueError("Selecciona un turno y un láser válidos.") from None
    if shift not in (1, 2) or not 1 <= laser <= 11:
        raise ValueError("Selecciona un turno y un láser válidos.")
    return data["day"], shift, laser


def assign(db, data):
    location = slot(data)
    code = data.get("employee", "")
    if not code:
        db.execute("DELETE FROM assignments WHERE day = ? AND shift = ? AND laser = ?", location)
        return
    operator = db.execute("SELECT 1 FROM employees WHERE code = ? AND role = 'operator' AND active = 1", (code,)).fetchone()
    if not operator:
        raise ValueError("Selecciona un operador registrado.")
    db.execute("""
        INSERT INTO assignments VALUES (?, ?, ?, ?)
        ON CONFLICT(day, shift, laser) DO UPDATE SET employee = excluded.employee
    """, (*location, code))


def record(db, user, data):
    location = slot(data)
    reference = data.get("reference", "").strip()
    pieces = data.get("pieces", "")
    request_id = data.get("id", "")
    if not (1 <= len(reference) <= 80 and re.fullmatch(r"[0-9]{1,6}", pieces)
            and 1 <= int(pieces) <= 100000 and re.fullmatch(r"[a-f0-9]{32}", request_id)):
        raise ValueError("Indica una orden o línea y una cantidad válida.")
    code = user["code"] if user["role"] == "operator" else data.get("employee", "")
    db.execute("""
        INSERT INTO production (id, day, shift, laser, employee, reference, pieces, recorded_by)
        SELECT ?, day, shift, laser, employee, ?, ?, ? FROM assignments
        WHERE day = ? AND shift = ? AND laser = ? AND employee = ?
        ON CONFLICT(id) DO NOTHING
    """, (request_id, reference, int(pieces), user["code"], *location, code))
    entry = db.execute("SELECT * FROM production WHERE id = ?", (request_id,)).fetchone()
    if not entry or tuple(entry)[1:] != (*location, code, reference, int(pieces), user["code"]):
        raise ValueError("La asignación o el registro cambió. Actualiza la pantalla.")


@app.post("/{action}")
async def mutate(action: str, request: Request):
    return await run_in_threadpool(handle_mutation, action, request, await fields(request))


def handle_mutation(action, request, data):
    shift = data.get("shift", "1")
    location = "/?turno=2" if shift == "2" else "/"
    if action in ("assign", "production") and re.fullmatch(r"(?:[1-9]|1[01])", data.get("laser", "")):
        location = f'/?turno={shift if shift == "2" else "1"}&laser={data["laser"]}'
    if action in ("employees", "reset-account", "remove-account"):
        location += "#cuentas"
    response = RedirectResponse(location, status_code=303)
    if action == "login":
        with database() as db:
            token, error, status = login(db, request, data)
        if not token:
            return render(request, error, status)
        cookie(response, "corte_session", token)
        return response
    try:
        with database() as db:
            db.execute("BEGIN IMMEDIATE")
            user = employee(db, request)
            if not user:
                raise HTTPException(401)
            if action == "logout":
                db.execute("DELETE FROM sessions WHERE token = ?",
                           (digest(request.cookies.get("corte_session", "")),))
                response.delete_cookie("corte_session")
            elif action == "password":
                password = data.get("password", "")
                if not user["pending"]:
                    raise HTTPException(403)
                if not 8 <= len(password) <= 128 or password == INITIAL_PASSWORD or password != data.get("confirm"):
                    raise ValueError("Usa al menos 8 caracteres y escribe la misma contraseña en ambos campos.")
                db.execute("UPDATE employees SET password = ?, pending = 0 WHERE code = ?",
                           (password_hash(password), user["code"]))
                db.execute("DELETE FROM sessions WHERE employee = ?", (user["code"],))
                token = token_urlsafe(32)
                db.execute("INSERT INTO sessions VALUES (?, ?, ?)",
                           (digest(token), user["code"], int(time()) + 28800))
                cookie(response, "corte_session", token)
            elif user["pending"]:
                raise HTTPException(403)
            elif action in ("employees", "reset-account", "remove-account") and user["role"] in ("developer", "supervisor"):
                manage_account(db, user, action, data)
            elif action == "assign" and user["role"] in ("developer", "supervisor"):
                assign(db, data)
            elif action == "production" and user["role"] in ("developer", "operator"):
                record(db, user, data)
            else:
                raise HTTPException(403)
    except sqlite3.IntegrityError:
        error = ("Ese operador ya tiene otro láser en el mismo turno." if action == "assign"
                 else "Ese código de empleado ya existe.")
        return render(request, error, 409)
    except ValueError as exc:
        return render(request, str(exc), 400)
    return response


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crear la cuenta inicial de Desarrollador.")
    parser.add_argument("codigo")
    parser.add_argument("nombre")
    args = parser.parse_args()
    setup()
    try:
        with database() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM employees WHERE role = 'developer'").fetchone():
                parser.exit(1, "Ya existe una cuenta de Desarrollador.\n")
            create_employee(db, args.codigo, args.nombre, "developer")
    except (ValueError, sqlite3.IntegrityError) as exc:
        parser.exit(1, f"{exc}\n")
