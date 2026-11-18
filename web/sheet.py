"""Server-rendered production grid and native form fallback."""
from html import escape
from secrets import token_hex
from urllib.parse import urlencode

COLUMNS = (
    ("A", "FECHA", "day"), ("B", "# DE ORDEN", "order_number"),
    ("C", "LINEA", "line"), ("D", "# PIEZAS", "pieces"),
    ("E", "COMENTARIOS", "comments"), ("F", "* REPRINT *", None),
    ("G", "Orden + Línea", None), ("H", "REPETICIONES", None),
    ("I", "SKU", "sku"), ("J", "CPA (SUPERVISOR)", None),
    ("K", "DUP.", None), ("L", "Operario", "employee"),
    ("M", "Estado", None), ("N", "Láser", None),
    ("O", "Turno", None), ("P", "Semana", None),
)
COMPUTED = {"F", "G", "H", "J", "K"}
NUMERIC = {"D", "H", "K"}
STATUS = {"approved": "Confirmado", "pending": "Duplicado · Por revisar", "rejected": "Descartado"}


def hidden(name, value):
    return f'<input type="hidden" name="{name}" value="{escape(str(value))}">'


def form(action, csrf, fields):
    return f'<form method="post" action="/{action}">{hidden("csrf", csrf)}{fields}</form>'


def query_link(**values):
    return "/?" + escape(urlencode(values))


def cells_for(row, counts):
    return {
        "A": row["day"], "B": row["order_number"], "C": row["line"], "D": row["pieces"],
        "E": row["comments"], "F": "*" if counts and counts["reprint"] else "",
        "G": row["order_line"],
        "H": counts["local"] if counts else 0, "I": row["sku"], "J": "—",
        "K": counts["total"] if counts else 0,
        "L": "" if row["employee"] == "@HISTORIA" else row["employee"],
        "M": STATUS[row["review"]], "N": row["laser"], "O": row["shift"], "P": row["week"],
    }


def equation(letter, index):
    return {
        "F": f'=SI(ES_REPRINT(G{index});"*";"")',
        "G": f'=SIN_SO(B{index})&"-"&MAYÚSC(C{index})',
        "H": f'=CONTAR_EN_LÁSER_Y_TURNO(G{index})',
        "J": "Pendiente de integración con CPA",
        "K": f'=CONTAR_EN_PRODUCCIÓN(G{index})',
    }.get(letter, "")


def cell_editor(letter, field, value, form_id, options):
    attrs = f'form="{form_id}" name="{field}" aria-labelledby="col-{letter} name-{letter}"'
    if field == "employee":
        choices = dict(options)
        if value and value not in choices:
            choices[value] = value
        items = ['<option value="">Selecciona</option>']
        items.extend(f'<option value="{escape(code)}" {"selected" if value == code else ""}>'
                     f'{escape(name)} · {escape(code)}</option>' for code, name in choices.items())
        return f'<select {attrs}>{"".join(items)}</select>'
    if field == "pieces":
        attrs += ' type="number" min="1" max="100000" required'
    elif field == "day":
        attrs += ' type="date" required'
    else:
        size = {"order_number": 27, "line": 12, "comments": 300, "sku": 60}[field]
        attrs += f' maxlength="{size}"'
        if field in ("order_number", "line"):
            attrs += " required"
        if field == "order_number":
            attrs += ' inputmode="numeric"'
            if not value:
                attrs += ' placeholder="Escribe y pulsa Enter"'
    return f'<input {attrs} value="{escape(str(value))}">'


def row_markup(row, new, index, columns, role, editable, colleague, values, options, csrf, scope,
               revision, audit_url, history, source):
    form_id = f"save-row-{index}"
    row_id = row["id"] if not new else token_hex(16)
    action = "production" if new else "edit-production"
    specific = hidden("id" if new else "record", row_id)
    scope += hidden("origen", source)
    if not new:
        specific += hidden("revision", revision)
    post = (f'<form id="{form_id}" method="post" action="/{action}">'
            f'{hidden("csrf", csrf)}{scope}{specific}</form>') if editable else ""
    menu = []
    if editable:
        menu.append(f'<button class="quiet row-save" form="{form_id}">Guardar fila</button>')
    if audit_url:
        menu.append(f'<a class="text-action" href="{audit_url}">Historial de cambios</a>')
    if editable and not new and not history and row["deletable"]:
        removal = form("delete-production", csrf, scope + specific
                       + '<button class="danger">Confirmar eliminación</button>')
        menu.append(f'<details><summary>Eliminar</summary>{removal}</details>')
    actions = (f'<details class="row-menu"><summary aria-label="Opciones de fila {index}">'
               f'<span>{index}</span><span aria-hidden="true">⋯</span></summary>'
               f'<div>{"".join(menu)}</div></details><span class="grid-print">{index}</span>') if menu else str(index)
    style = ' class="colleague"' if colleague else (' class="append-row"' if new else '')
    rendered = []
    for letter, _, field in columns:
        writable = editable and bool(field) and (letter != "A" or new)
        value = values.get(letter, "")
        classes = ["grid-cell", f"grid-{letter}"]
        if letter in COMPUTED:
            classes.append("formula-cell")
        if letter in NUMERIC:
            classes.append("number")
        body = escape(str(value))
        if writable:
            body = (cell_editor(letter, field, value, form_id, options)
                    + f'<span class="grid-print">{escape(str(value))}</span>')
        elif letter == "M" and value:
            body = f'<span class="pill {row["review"]}">{body}</span>'
        formula = equation(letter, index)
        rendered.append(f'<td class="{" ".join(classes)}" role="gridcell" '
                        f'aria-describedby="col-{letter} name-{letter}" aria-readonly="{str(not writable).lower()}" '
                        f'data-letter="{letter}" data-formula="{escape(formula)}">{body}</td>')
    return (f'<tr{style} data-record="{escape(row_id)}" role="row"><th scope="row" class="row-number">'
            f'{post}{actions}</th>{"".join(rendered)}</tr>')


def grid(rows, counts, user, csrf, scope, totals, new_row=None, history=False,
         revision_of=lambda row: 0, audit_of=lambda row: "", message="", week="", source="turno"):
    role = user["role"]
    columns = tuple(c for c in COLUMNS[:16 if history else 13] if role != "operator" or c[0] != "L")
    colgroup = '<colgroup><col class="index-col">' + "".join(
        f'<col class="col-{letter}">' for letter, *_ in columns) + '</colgroup>'
    letters = "<tr><td></td>" + "".join(
        f'<th id="col-{letter}" scope="col" class="grid-{letter}">{letter}</th>' for letter, *_ in columns) + "</tr>"
    names = "<tr><th scope=\"col\"><span class=\"sr-only\">Fila</span></th>" + "".join(
        f'<th id="name-{letter}" scope="col" class="grid-{letter}">{name}</th>'
        for letter, name, _ in columns) + "</tr>"
    body = []
    for n, row in enumerate(rows, 1):
        acl = row["access"]
        body.append(row_markup(
            row, False, n, columns, role, acl, role == "operator" and row["employee"] != user["code"],
            cells_for(row, counts.get(row["id"])), row["employee_options"], csrf,
            scope + hidden("day", row["day"]) + (hidden("shift", row["shift"]) + hidden("laser", row["laser"]) if history else ""),
            revision_of(row) if acl else 0, audit_of(row), history, source))
    if new_row:
        day, options = new_row
        body.append(row_markup({}, True, len(rows) + 1, columns, role, True, False,
                               {"A": day, "L": options[0][0] if options else ""}, options, csrf, scope,
                               0, "", False, source))
    footer = (f'<tfoot><tr><th scope="row" class="total-label">Total</th><td colspan="3"></td>'
              f'<td class="number" aria-label="Total confirmado" data-formula="=SUMA(D:D)">{totals:,}</td>'
              f'<td colspan="{len(columns) - 4}"></td></tr></tfoot>')
    return f"""<div class="workbook" data-user-role="{role}" data-week="{escape(week)}">
        <div class="formula-bar" hidden><output aria-label="Celda seleccionada">—</output>
        <b aria-hidden="true">fx</b><span aria-label="Contenido de la celda"></span></div>
        <div class="sheet grid-scroll"><table class="production-grid" role="grid"
         aria-label="{'Historia' if history else 'Hoja del láser'}" aria-rowcount="{len(body) + 3}" aria-colcount="{len(columns) + 1}">
        {colgroup}<thead>{letters}{names}</thead><tbody>{''.join(body)}</tbody>{footer}</table></div>
        <p class="sheet-status" role="status" aria-live="polite">{escape(message)}</p></div>"""
