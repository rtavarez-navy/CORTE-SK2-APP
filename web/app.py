"""CORTE SK2, servidor web de planta."""
import argparse
from contextlib import asynccontextmanager, contextmanager
from datetime import date, datetime, timezone
from hashlib import pbkdf2_hmac, sha256
from hmac import compare_digest
from html import escape
import json
import os
from pathlib import Path
import re
from secrets import token_hex, token_urlsafe
import sqlite3
from time import time
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from web import cpa, production as ledger

WEB_ROOT = Path(__file__).parent
INITIAL_PASSWORD = "12345"
ROLES = {"developer": "Desarrollador", "supervisor": "Supervisor", "operator": "Operador"}
ZONE = ZoneInfo("America/Santo_Domingo")
ASSIGNMENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS assignments (
    day TEXT NOT NULL, shift INTEGER NOT NULL CHECK (shift IN (1, 2)),
    laser INTEGER NOT NULL CHECK (laser BETWEEN 1 AND 11),
    position INTEGER NOT NULL CHECK (position IN (1, 2)),
    employee TEXT NOT NULL REFERENCES employees(code),
    PRIMARY KEY (day, shift, laser, position), UNIQUE (day, shift, employee)
);
"""
SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    code TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
    password TEXT NOT NULL, pending INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY, employee TEXT NOT NULL REFERENCES employees(code),
    expires INTEGER NOT NULL
);
""" + ASSIGNMENTS_SCHEMA + """
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

        assignment_columns = {row["name"] for row in db.execute("PRAGMA table_info(assignments)")}
        if "position" not in assignment_columns:
            db.execute("ALTER TABLE assignments RENAME TO assignments_previous")
            db.execute(ASSIGNMENTS_SCHEMA)
            db.execute("""
                INSERT INTO assignments (day, shift, laser, position, employee)
                SELECT day, shift, laser, 1, employee FROM assignments_previous
            """)
            db.execute("DROP TABLE assignments_previous")
        production_columns = {row["name"] for row in db.execute("PRAGMA table_info(production)")}
        if "review" not in production_columns:
            db.execute("""
                ALTER TABLE production ADD COLUMN review TEXT NOT NULL DEFAULT 'approved'
                CHECK (review IN ('approved', 'pending', 'rejected'))
            """)
            db.execute("ALTER TABLE production ADD COLUMN reviewed_by TEXT REFERENCES employees(code)")
        ledger.migrate(db)


@asynccontextmanager
async def lifespan(_app):
    await run_in_threadpool(setup)
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=WEB_ROOT / "static"), name="static")


@app.middleware("http")
async def headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'self'; img-src 'self'; font-src 'self'; script-src 'self'; form-action 'self'; "
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


def page(title, content, error="", status=200, layout="login", header_actions=""):
    alert = f'<p role="alert" class="alert">{escape(error)}</p>' if error else ""
    return HTMLResponse(f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} · Corte SK2</title><link rel="stylesheet" href="/style.css">
<link rel="icon" type="image/png" sizes="32x32" href="/static/favicon.png">
<link rel="apple-touch-icon" sizes="180x180" href="/static/favicon-180.png">
{('<script src="/static/report.js" defer></script>' if layout == 'report' else '')}
</head><body class="{layout}">
<header class="site-header"><div class="frame header-inner">
    <a href="/" class="brand">
        <img src="/static/logo-mark.png" width="40" height="40" alt="">
        <span><strong>CORTE SAKIRA 2</strong><small>&amp; Proyecto Ámbar</small></span>
    </a>{header_actions}
</div></header>
<main class="frame">{alert}{content}</main></body></html>""", status)


@app.get("/style.css")
def stylesheet():
    return FileResponse(WEB_ROOT / "style.css", media_type="text/css")


def login_layout(content):
    return f"""<div class="auth-layout">
        <img class="full-logo" src="/static/logo-full.png"
             alt="CORTE SAKIRA 2 y Proyecto Ámbar" width="768" height="416">
        <section class="auth-panel">{content}</section>
    </div>"""


def render(request, error="", status=200, query=None):
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
            response = page("Inicio de sesión", login_layout(contents), error, status)
        elif user["pending"]:
            contents = '<h1>Cambia tu contraseña</h1><p>Usa al menos 8 caracteres para continuar.</p>' + form("password", csrf, """
                <label>Nueva contraseña<input type="password" name="password" autocomplete="new-password" minlength="8" maxlength="128" required></label>
                <label>Confirmar contraseña<input type="password" name="confirm" autocomplete="new-password" minlength="8" maxlength="128" required></label>
                <button>Guardar y continuar</button>""") + form("logout", csrf, '<button class="quiet">Cerrar sesión</button>')
            response = page("Primer acceso", login_layout(contents), error, status)
        else:
            response = dashboard(db, request, user, csrf, error, status, query)
    if not request.cookies.get("corte_csrf"):
        cookie(response, "corte_csrf", csrf)
    return response


def dashboard(db, request, user, csrf, error, status, query=None):
    current_day = today()
    operator = user["role"] == "operator"
    query = request.query_params if query is None else query
    day = current_day
    if not operator and query.get("fecha"):
        try:
            day = date.fromisoformat(query["fecha"]).isoformat()
        except ValueError:
            pass
    shift = 2 if query.get("turno") == "2" else 1
    view = query.get("vista", "turno" if query.get("turno") else "panel")
    staff = {row["code"]: row["name"] for row in db.execute(
        "SELECT code, name FROM employees WHERE role = 'operator' AND active = 1 ORDER BY name, code")}
    slots = db.execute("SELECT * FROM assignments WHERE day = ? ORDER BY position, shift, laser", (day,)).fetchall()
    assigned_codes = {row["employee"] for row in db.execute(
        "SELECT employee FROM assignments WHERE day = ?", (current_day,))}
    waiting = {code: name for code, name in staff.items() if code not in assigned_codes}
    pending = db.execute("""
        SELECT * FROM production WHERE review = 'pending' AND deleted_at IS NULL ORDER BY day, rowid
    """).fetchall() if not operator else []
    logout = form("logout", csrf, '<button class="quiet">Cerrar sesión</button>')
    identity = f"{escape(user['name'])} · {ROLES[user['role']]}"
    if operator:
        current = next((row for row in slots if row["employee"] == user["code"]), None)
        if not current:
            body = """<section><h1>Esperando asignación</h1>
                <p>Tu supervisor te asignará un láser y un turno.</p>
                <a class="text-action" href="/">Actualizar asignación</a></section>"""
            header_actions = logout
        else:
            shift, number = current["shift"], current["laser"]
            station = f"Láser {number} · Turno {shift}"
            header_actions = f'<span class="station-context">{station}</span>{logout}'
            rows = db.execute("""
                SELECT * FROM production WHERE day = ? AND shift = ? AND laser = ? AND deleted_at IS NULL
                ORDER BY rowid
            """, (day, shift, number)).fetchall()
            body = laser_report(db, day, shift, number, [current], rows, staff, user, csrf, query)
        return page("Estación", body, error, status, "station", header_actions)

    date_suffix = "&fecha=" + day if day != current_day else ""
    links = [
        ("panel", "/?vista=panel" + date_suffix, "Resumen"),
        ("turno1", "/?vista=turno&turno=1" + date_suffix, "Turno 1"),
        ("turno2", "/?vista=turno&turno=2" + date_suffix, "Turno 2"),
        ("personal", "/?vista=personal", "Personal"),
        ("avisos", "/?vista=avisos", f"Notificaciones ({len(pending) + len(waiting)})"),
    ]
    selected = f"turno{shift}" if view == "turno" else view
    nav = '<nav aria-label="Secciones">' + "".join(
        f'<a href="{escape(url)}" {"aria-current=page" if key == selected else ""}>{label}</a>'
        for key, url, label in links
    ) + '</nav>'
    layout = "dashboard"
    if view == "personal":
        title = "Personal"
        body = accounts_panel(db, user, csrf) + reprints_panel(db, csrf)
    elif view == "avisos":
        title = "Notificaciones"
        body = notifications(db, waiting, pending, staff, csrf)
    else:
        production = db.execute(
            "SELECT * FROM production WHERE day = ? AND deleted_at IS NULL ORDER BY rowid", (day,)
        ).fetchall()
        if view == "turno":
            laser = query.get("laser", "")
            if laser in {str(number) for number in range(1, 12)}:
                number = int(laser)
                title = f"Reporte · Láser {number}"
                layout = "report"
                back = f'<a class="text-action" href="/?vista=turno&amp;turno={shift}{escape(date_suffix)}">← Láseres del turno {shift}</a>'
                body = laser_report(
                    db, day, shift, number,
                    [row for row in slots if row["shift"] == shift and row["laser"] == number],
                    [row for row in production if row["shift"] == shift and row["laser"] == number],
                    staff, user, csrf, query, back)
            else:
                title = f"Láseres del turno {shift}"
                body = shift_grid(shift, slots, production, staff, date_suffix, heading=False)
        else:
            title = "Resumen de producción"
            body = overview(slots, production, len(pending), current_day, day, staff, date_suffix)
    if layout == "report":
        return page(title, nav + body, error, status, layout, logout)

    date_filter = ""
    if view in ("panel", "turno"):
        date_filter = f"""<form class="report-filter" method="get" action="/">
            {hidden("vista", view)}{hidden("turno", shift)}
            <label>Fecha de producción<input name="fecha" type="date" value="{day}" required></label>
            <button class="quiet">Ver fecha</button></form>"""
    heading = f'<div class="page-heading"><div><h1>{title}</h1><p>{identity}</p></div>{date_filter}</div>'
    return page(title, nav + heading + body, error, status, layout, logout)


def overview(slots, production, duplicate_count, current_day, day, staff, date_suffix):
    units = {shift: sum(row["pieces"] for row in production
                        if row["shift"] == shift and row["review"] == "approved") for shift in (1, 2)}
    duplicate_notice = ""
    if duplicate_count:
        noun = "Duplicado pendiente" if duplicate_count == 1 else "Duplicados pendientes"
        duplicate_notice = f"""<div class="alert notice-row">
            <strong>{duplicate_count} · {noun}</strong>
            <a class="text-action" href="/?vista=avisos">Revisar duplicados</a></div>"""
    metrics = [
        ("Piezas hoy" if day == current_day else "Piezas confirmadas", sum(units.values())),
        ("Turno 1", units[1]),
        ("Turno 2", units[2]),
        ("Por revisar", duplicate_count),
    ]
    cards = "".join(f'<article><p>{label}</p><strong class="number">{value:,}</strong></article>'
                    for label, value in metrics)
    grids = "".join(shift_grid(shift, slots, production, staff, date_suffix) for shift in (1, 2))
    return f'<div class="metrics">{cards}</div>{duplicate_notice}{grids}'


def shift_grid(shift, slots, production, staff, date_suffix, heading=True):
    cards = []
    for laser in range(1, 12):
        operators = [row["employee"] for row in slots if row["shift"] == shift and row["laser"] == laser]
        names = ", ".join(escape(staff.get(code, code)) for code in operators)
        pieces = sum(row["pieces"] for row in production
                     if row["shift"] == shift and row["laser"] == laser and row["review"] == "approved")
        staffing = ("Sin operario", "1 operario", "2 operarios")[len(operators)]
        operator_names = f"<p>{names}</p>" if names else ""
        cards.append(f"""<a class="laser-card staffing-{len(operators)}"
            href="/?vista=turno&amp;turno={shift}&amp;laser={laser}{escape(date_suffix)}">
            <div class="machine"><strong>Láser {laser}</strong><span class="staff-status">{staffing}</span></div>
            <p class="laser-pieces"><b class="number">{pieces:,}</b> piezas</p>{operator_names}</a>""")
    title = f"<h2>Turno {shift}</h2>" if heading else ""
    return f'<section class="shift-section">{title}<div class="laser-grid">{"".join(cards)}</div></section>'


def laser_report(db, day, shift, laser, slots, rows, staff, user, csrf, query, back=""):
    scope = hidden("day", day) + hidden("shift", shift) + hidden("laser", laser)
    operator = user["role"] == "operator"
    assignment = ""
    if not operator and day == today():
        choices = []
        for position in (1, 2):
            current = next((row["employee"] for row in slots if row["position"] == position), "")
            options = "".join(f'<option value="{escape(code)}" {"selected" if code == current else ""}>'
                              f'{escape(name)} · {escape(code)}</option>' for code, name in staff.items())
            choices.append(f'<label>Operario {position}<select name="employee{position}">'
                           f'<option value="">Sin asignar</option>{options}</select></label>')
        assignment = '<div class="assignment">' + form(
            "assign", csrf, scope + "".join(choices) + '<button>Guardar asignación</button>') + '</div>'
    totals = sum(row["pieces"] for row in rows if row["review"] == "approved")
    counts = ledger.report_counts(db, rows, shift, laser)
    search = query.get("orden", "").strip()[:80]
    search_key = re.sub(r"[\s/]+", "", search.upper()).removeprefix("SO-")
    selected = [row for row in rows if search_key in row["order_line"]
                or search.upper() in row["reference"].upper()]
    report = "".join(report_row(row, counts.get(row["order_line"]), user, csrf, scope)
                     for row in selected)
    capture = ""
    if day == today() and slots and (operator or user["role"] == "developer"):
        picker = ""
        if not operator:
            options = "".join(f'<option value="{escape(row["employee"])}">{escape(row["employee"])}</option>'
                              for row in slots)
            picker = f'<label>Operario<select name="employee">{options}</select></label>'
        saved_id = query.get("guardado")
        saved = next((row for row in rows if row["id"] == saved_id
                      and row["recorded_by"] == user["code"]), None)
        notice = ""
        if saved and saved["review"] == "pending":
            notice = (f'<p class="alert" role="status"><strong>Duplicado.</strong> '
                      f'La orden {escape(saved["order_number"])} · línea {escape(saved["line"])} '
                      'quedó pendiente. Espera la revisión del supervisor.</p>')
        elif saved and saved["review"] == "approved":
            notice = '<p class="confirmation" role="status">Pieza guardada.</p>'
        capture = '<section class="capture"><h2>Captura de piezas</h2>' + notice + form(
            "production", csrf, scope + hidden("id", token_hex(16))
            + production_fields() + picker + '<button>Guardar pieza</button>') + '</section>'
    empty_message = "Sin registros para esta búsqueda." if search else "Sin registros en esta fecha y turno."
    report = report or f'<tr><td colspan="13">{empty_message}</td></tr>'
    report_scope = hidden("vista", "turno") + hidden("laser", laser)
    date_shift = ""
    if not operator:
        shift_options = "".join(
            f'<option value="{n}" {"selected" if n == shift else ""}>Turno {n}</option>' for n in (1, 2))
        date_shift = f"""<label>Fecha de producción<input name="fecha" type="date" value="{day}" required></label>
            <label>Turno<select name="turno">{shift_options}</select></label>"""
    else:
        date_shift = hidden("fecha", day) + hidden("turno", shift)
    filters = f"""<form class="report-filter" method="get" action="/">
        {report_scope}{date_shift}
        <label>Buscar orden<input type="search" name="orden" value="{escape(search)}" maxlength="80"></label>
        <button class="quiet">{"Buscar" if operator else "Aplicar filtros"}</button></form>"""
    history = audit_panel(db, user, query.get("historial"), day, shift, laser)
    deleted_sql = "SELECT * FROM production WHERE day = ? AND shift = ? AND laser = ? AND deleted_at IS NOT NULL"
    deleted_args = (day, shift, laser)
    if operator:
        deleted_sql += " AND employee = ?"
        deleted_args += (user["code"],)
    deleted_links = "".join(
        f'<li>{audit_link(row, row["reference"])}</li>' for row in db.execute(deleted_sql, deleted_args))
    deleted = (f'<details><summary>Registros eliminados</summary><ul>{deleted_links}</ul></details>'
               if deleted_links else "")
    title = f"Láser {laser} · Turno {shift}"
    heading = f"""<div class="page-heading"><div>{back}<h1>{title}</h1>
        <p>{day} · {totals:,} piezas confirmadas</p>
        {f'<p>Orden buscada: {escape(search)}</p>' if search else ''}</div>
        {'' if operator else '<button class="quiet print-button" type="button" hidden>Imprimir reporte</button>'}</div>"""
    if assignment:
        assignment = f'<details class="assignment"><summary>Asignar operarios</summary>{assignment}</details>'
    cpa_scope = report_scope + hidden("fecha", day) + hidden("turno", shift) + hidden("orden", search)
    cpa_lookup = cpa_panel(cpa_scope, query.get("consulta_cpa"))
    return f"""{heading}{capture}
        <section class="report-section"><div class="report-tools">{filters}{assignment}</div>
        <div class="sheet production-sheet" tabindex="0" role="region" aria-label="Tabla de producción">
        <table aria-label="Reporte del láser {laser}"><thead><tr>
        <th scope="col">FECHA</th><th scope="col"># DE ORDEN</th><th scope="col">LINEA</th>
        <th scope="col" class="number"># PIEZAS</th><th scope="col">COMENTARIOS</th>
        <th scope="col">* REPRINT *</th><th scope="col">Orden + Linea</th>
        <th scope="col" class="number">REPETICIONES</th><th scope="col">SKU</th><th scope="col">CPA (SUPERVISOR)</th>
        <th scope="col" class="number">DUP.</th><th scope="col">Operario</th><th scope="col">Estado y acciones</th>
        </tr></thead><tbody>{report}</tbody><tfoot><tr>
        <th scope="row" colspan="3">Total del día · Turno {shift}</th>
        <td class="number">{totals:,}</td><td colspan="9">Piezas confirmadas</td>
        </tr></tfoot></table></div>{cpa_lookup}{deleted}{history}</section>"""


def cpa_panel(scope, query):
    value = (query or "")[:40]
    result = ""
    if query is not None:
        try:
            rows = cpa.lookup(query)
        except (ValueError, cpa.CpaUnavailable) as exc:
            result = f'<p class="alert" role="status">{escape(str(exc))}</p>'
        else:
            body = "".join(
                f"<tr><td>{escape(row.order)}</td><td>{escape(row.set or '—')}</td>"
                f"<td>{escape(row.quantity)}</td><td>{escape(row.status)}</td></tr>"
                for row in rows
            )
            if body:
                result = f"""<div class="sheet"><table aria-label="Resultados de CPA"><thead><tr>
                    <th>Orden</th><th>Set</th><th class="number">Cantidad CPA</th><th>Estado de línea</th>
                    </tr></thead><tbody>{body}</tbody></table></div>"""
            else:
                result = '<p role="status">CPA no devolvió líneas para esa orden y Set en JuiceSakira2.</p>'
    return f"""<details class="cpa-lookup" id="consulta-cpa" {'open' if query is not None else ''}>
        <summary>Consultar orden en CPA</summary>
        <form method="get" action="/#consulta-cpa">{scope}
        <label>Orden y línea<input name="consulta_cpa" value="{escape(value)}"
        placeholder="3986055 A" maxlength="40" required></label>
        <button>Buscar en CPA</button></form>{result}</details>"""


def production_fields(row=None):
    values = dict(row) if row is not None else {}
    def value(key):
        return escape(str(values.get(key, "")))
    return f"""<label class="field-order">Orden<input name="order_number" value="{value('order_number')}"
        inputmode="numeric" maxlength="27" required></label>
        <label class="field-line">Línea<input name="line" value="{value('line')}" autocapitalize="characters" maxlength="12" required></label>
        <label class="field-pieces">Piezas<input name="pieces" type="number" value="{value('pieces')}" min="1" max="100000" required></label>
        <label class="field-comments">Comentario<input name="comments" value="{value('comments')}" maxlength="300"></label>
        <label class="field-sku">SKU<input name="sku" value="{value('sku')}" maxlength="60"></label>"""


def report_row(row, counts, user, csrf, scope):
    statuses = {"approved": "Confirmado", "pending": "Duplicado · Por revisar", "rejected": "Descartado"}
    colleague = user["role"] == "operator" and row["employee"] != user["code"]
    controls = ""
    if user["role"] == "developer" or (user["role"] == "operator" and row["employee"] == user["code"]):
        key = scope + hidden("record", row["id"])
        edit = form("edit-production", csrf, key + production_fields(row) + '<button>Guardar corrección</button>')
        delete = form("delete-production", csrf, key + '<button class="danger">Confirmar eliminación</button>')
        controls = f'<details><summary>Corregir</summary>{edit}</details><details><summary>Eliminar</summary>{delete}</details>'
    link = ""
    if user["role"] != "operator" or row["employee"] == user["code"]:
        link = audit_link(row, "Historial")
    actions = f'<details class="row-actions"><summary>Acciones</summary>{controls}{link}</details>' if controls or link else ""
    return f"""<tr{' class="colleague"' if colleague else ''}><td>{escape(row['day'])}</td><td>{escape(row['order_number'])}</td>
        <td>{escape(row['line'])}</td><td class="number">{row['pieces']:,}</td><td>{escape(row['comments'])}</td>
        <td>{'*' if counts and counts['reprint'] else ''}</td>
        <td>{escape(row['order_line'])}</td><td class="number">{counts['local'] if counts else 0}</td>
        <td>{escape(row['sku'])}</td><td>—</td><td class="number">{counts['total'] if counts else 0}</td>
        <td>{escape(row['employee'])}</td><td><span class="pill {row['review']}">{statuses[row['review']]}</span>
        {actions}</td></tr>"""


def audit_link(row, label):
    url = urlencode({"vista": "turno", "fecha": row["day"], "turno": row["shift"],
                     "laser": row["laser"], "historial": row["id"]})
    return f'<a href="/?{escape(url)}#historial">{escape(label)}</a>'


def audit_panel(db, user, record_id, day, shift, laser):
    if not record_id:
        return ""
    row = ledger.get_record(db, record_id)
    if not row or (row["day"], row["shift"], row["laser"]) != (day, shift, laser):
        return ""
    if user["role"] == "operator" and row["employee"] != user["code"]:
        return ""
    def snapshot(payload):
        if not payload:
            return "—"
        row = json.loads(payload)
        text = f"{row['order_number']} / {row['line']} · {row['pieces']} piezas · {row['review']}"
        if row['deleted_at']:
            text += " · Eliminado"
        if row["sku"] or row["comments"]:
            text += f" · SKU: {row['sku']} · {row['comments']}"
        return escape(text)
    items = "".join(
        f"<tr><td>{escape(item['occurred_at'])}</td><td>{escape(item['actor'])}</td>"
        f"<td>{escape(item['event'])}</td><td>{snapshot(item['previous'])}</td><td>{snapshot(item['current'])}</td></tr>"
        for item in db.execute("SELECT * FROM production_audit WHERE record_id = ? ORDER BY sequence DESC", (record_id,))
    )
    return f"""<div id="historial"><h3>Historial de cambios</h3><div class="sheet"><table>
        <thead><tr><th>Fecha UTC</th><th>Responsable</th><th>Acción</th><th>Antes</th><th>Después</th></tr></thead>
        <tbody>{items or '<tr><td colspan="5">Registro anterior al historial de cambios.</td></tr>'}</tbody></table></div></div>"""


def reprints_panel(db, csrf):
    rows = "".join(
        f'<li>{escape(row["order_number"])} / {escape(row["line"])} '
        + form("reprint", csrf, hidden("key", row["order_line"]) + '<button class="quiet">Quitar</button>') + '</li>'
        for row in db.execute("SELECT * FROM valid_reprints ORDER BY order_line")
    )
    controls = form("reprint", csrf, """<label># de orden<input name="order_number" maxlength="27" required></label>
        <label>Línea<input name="line" maxlength="12" required></label><button>Autorizar reprint</button>""")
    return f'<section id="reprints"><h2>Reprints válidos</h2>{controls}<ul>{rows}</ul></section>'


def notifications(db, waiting, pending, staff, csrf):
    queue = []
    for row in pending:
        previous = db.execute("""
            SELECT day, shift, laser, pieces FROM production
            WHERE order_line = ? AND review = 'approved' AND deleted_at IS NULL
            ORDER BY rowid DESC LIMIT 1
        """, (row["order_line"],)).fetchone()
        context = (f'<small>Confirmado: {previous["day"]} · T{previous["shift"]} · '
                   f'Láser {previous["laser"]} · {previous["pieces"]:,} piezas</small>'
                   if previous else '<small>Sin otro registro confirmado</small>')
        fields = hidden("record", row["id"])
        controls = form("review", csrf, fields + """
            <div class="review-actions"><button name="decision" value="approved">Conservar</button>
            <button class="danger" name="decision" value="rejected">Descartar</button></div>""")
        queue.append(f"""<tr><td>{escape(row['reference'])}{context}</td><td>{row['day']} · T{row['shift']} · Láser {row['laser']}</td>
            <td>{escape(staff.get(row['employee'], row['employee']))}</td><td>{row['pieces']:,}</td><td>{controls}</td></tr>""")
    waits = "".join(f'<li>{escape(name)} · {escape(code)}</li>' for code, name in waiting.items())
    duplicates = "".join(queue) or '<tr><td colspan="5">Sin duplicados pendientes.</td></tr>'
    return f"""<section><h2>Órdenes duplicadas</h2><div class="sheet"><table>
        <thead><tr><th>Orden / línea</th><th>Registro</th><th>Operario</th><th>Piezas</th><th>Decisión</th></tr></thead>
        <tbody>{duplicates}</tbody></table></div></section>
        <section><h2>Operarios esperando asignación</h2>
        {f'<ul>{waits}</ul>' if waits else '<p>Todos los operarios activos tienen asignación.</p>'}
        <p><a href="/?vista=turno&amp;turno=1">Ir al Turno 1</a> · <a href="/?vista=turno&amp;turno=2">Ir al Turno 2</a></p></section>"""


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
        parsed = parse_qs(body.decode(), keep_blank_values=True, max_num_fields=16)
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
    codes = [data.get("employee1", ""), data.get("employee2", "")]
    if codes[0] and codes[0] == codes[1]:
        raise ValueError("Selecciona dos operarios distintos.")
    db.execute("DELETE FROM assignments WHERE day = ? AND shift = ? AND laser = ?", location)
    for position, code in enumerate(codes, 1):
        if not code:
            continue
        if not db.execute("SELECT 1 FROM employees WHERE code = ? AND role = 'operator' AND active = 1", (code,)).fetchone():
            raise ValueError("Selecciona un operario registrado.")
        db.execute("DELETE FROM assignments WHERE day = ? AND employee = ?", (location[0], code))
        db.execute("""
            INSERT INTO assignments (day, shift, laser, position, employee) VALUES (?, ?, ?, ?, ?)
        """, (*location, position, code))


def may_capture(db, user, location, code):
    if user["role"] == "operator":
        assignment = db.execute("""
            SELECT day, shift, laser FROM assignments WHERE day = ? AND employee = ?
            ORDER BY position, shift, laser LIMIT 1
        """, (location[0], code)).fetchone()
        return assignment is not None and tuple(assignment) == location
    return db.execute("""
        SELECT 1 FROM assignments WHERE day = ? AND shift = ? AND laser = ? AND employee = ?
    """, (*location, code)).fetchone() is not None


def record(db, user, data):
    location = slot(data)
    order, line, pieces, comments, sku, key = ledger.values(data)
    request_id = data.get("id", "")
    if not re.fullmatch(r"[a-f0-9]{32}", request_id):
        raise ValueError("Actualiza el reporte antes de registrar.")
    code = user["code"] if user["role"] == "operator" else data.get("employee", "")
    previous = ledger.get_record(db, request_id)
    if previous:
        frozen = ("day", "shift", "laser", "employee", "order_number", "line", "pieces",
                  "comments", "sku", "recorded_by")
        if tuple(previous[field] for field in frozen) != (*location, code, order, line, pieces,
                                                         comments, sku, user["code"]):
            raise HTTPException(409)
        return
    if not may_capture(db, user, location, code):
        raise HTTPException(403)
    db.execute("""
        INSERT INTO production (id, day, shift, laser, employee, reference, pieces, recorded_by, review,
                                order_number, line, comments, sku, order_line)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (request_id, *location, code, f"{order} / {line}", pieces, user["code"],
          ledger.review_status(db, key, request_id), order, line, comments, sku, key))
    ledger.audit(db, request_id, user["code"], "Registro")


def change_production(db, user, data, action):
    key = data.get("record", "")
    row = ledger.get_record(db, key)
    if not row or row["deleted_at"]:
        raise HTTPException(404)
    location = (row["day"], row["shift"], row["laser"])
    if user["role"] == "operator":
        if row["employee"] != user["code"] or row["day"] != today() or not may_capture(db, user, location, user["code"]):
            raise HTTPException(403)
    if action == "delete-production":
        db.execute("UPDATE production SET deleted_at = ? WHERE id = ?",
                   (datetime.now(timezone.utc).isoformat(timespec="seconds"), key))
        ledger.audit(db, key, user["code"], "Eliminación", row)
        return
    order, line, pieces, comments, sku, pair = ledger.values(data)
    review, reviewer = row["review"], row["reviewed_by"]
    if pair != row["order_line"] or (review == "rejected" and pieces != row["pieces"]):
        review, reviewer = ledger.review_status(db, pair, key), None
    db.execute("""
        UPDATE production SET order_number = ?, line = ?, pieces = ?, comments = ?, sku = ?,
               reference = ?, order_line = ?, review = ?, reviewed_by = ? WHERE id = ?
    """, (order, line, pieces, comments, sku, f"{order} / {line}", pair, review, reviewer, key))
    ledger.audit(db, key, user["code"], "Corrección", row)


@app.post("/{action}")
async def mutate(action: str, request: Request):
    return await run_in_threadpool(handle_mutation, action, request, await fields(request))


def handle_mutation(action, request, data):
    shift = data.get("shift", "1")
    location = "/?turno=2" if shift == "2" else "/"
    if action in ("assign", "production", "edit-production", "delete-production") and re.fullmatch(r"(?:[1-9]|1[01])", data.get("laser", "")):
        location = f'/?vista=turno&turno={shift if shift == "2" else "1"}&laser={data["laser"]}'
    if action in ("employees", "reset-account", "remove-account"):
        location = "/?vista=personal#cuentas"
    if action in ("edit-production", "delete-production"):
        try:
            location += "&fecha=" + date.fromisoformat(data.get("day", "")).isoformat()
        except ValueError:
            pass
    if action == "reprint":
        location = "/?vista=personal#reprints"
    if action == "review":
        location = "/?vista=avisos"
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
            elif action == "review" and user["role"] in ("developer", "supervisor"):
                decision = data.get("decision")
                if decision not in ("approved", "rejected"):
                    raise HTTPException(400)
                key = data.get("record", "")
                previous = ledger.get_record(db, key)
                updated = db.execute("""
                    UPDATE production SET review = ?, reviewed_by = ?
                    WHERE id = ? AND review = 'pending' AND deleted_at IS NULL
                """, (decision, user["code"], key))
                if updated.rowcount:
                    ledger.audit(db, key, user["code"], "Revisión de duplicado", previous)
            elif action == "reprint" and user["role"] in ("developer", "supervisor"):
                if data.get("key"):
                    db.execute("DELETE FROM valid_reprints WHERE order_line = ?", (data["key"],))
                else:
                    order, line = ledger.order_fields(data)
                    db.execute("INSERT OR IGNORE INTO valid_reprints VALUES (?, ?, ?)",
                               (ledger.reference_key(order, line), order, line))
            elif action in ("edit-production", "delete-production") and user["role"] in ("developer", "operator"):
                change_production(db, user, data, action)
            elif action == "production" and user["role"] in ("developer", "operator"):
                record(db, user, data)
                saved_query = urlencode({"vista": "turno", "turno": int(shift),
                                         "laser": int(data["laser"]), "guardado": data["id"]})
                response.headers["location"] = f"/?{saved_query}"
            else:
                raise HTTPException(403)
    except sqlite3.IntegrityError:
        error = ("Ese operador ya tiene otro láser en el mismo turno." if action == "assign"
                 else "Ese código de empleado ya existe.")
        return render(request, error, 409, dict(parse_qsl(urlsplit(location).query)))
    except ValueError as exc:
        return render(request, str(exc), 400, dict(parse_qsl(urlsplit(location).query)))
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
