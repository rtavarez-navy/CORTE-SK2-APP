"use strict";

const tableSelector = ".production-grid";
const editorSelector = "input:not([type=hidden]), select";
let book = document.querySelector(".workbook");

if (book) {
    let selected;
    let beforeEdit;
    let busy = false;
    let undo = null;
    let failedPaste = null;
    let originals;

    const rows = () => [...book.querySelectorAll("tbody tr")];
    const rowForm = (row) => row?.querySelector("th > form");
    const cells = (row) => [...row.querySelectorAll(".grid-cell")];
    const editor = (cell) => cell?.querySelector(editorSelector);
    const values = (form) => new URLSearchParams(new FormData(form));
    const status = (message, error = false) => {
        const line = book.querySelector(".sheet-status");
        line.textContent = message;
        line.classList.toggle("sheet-error", error);
    };

    function bind(next) {
        book = next;
        book.classList.add("enhanced");
        book.querySelector(".formula-bar").hidden = false;
        originals = new Map();
        for (const row of rows()) {
            const form = rowForm(row);
            if (form) originals.set(row.dataset.record, values(form));
            for (const cell of cells(row)) {
                cell.tabIndex = -1;
                const input = editor(cell);
                if (input) input.tabIndex = -1;
            }
        }
        const first = rows()[0];
        const initial = first && (first.querySelector(".grid-B") || cells(first)[0]);
        selected = undefined;
        if (initial) select(initial, false);
    }

    function cellValue(cell) {
        return editor(cell)?.value ?? cell.textContent.trim();
    }

    function formulaBar() {
        if (!selected) return;
        book.querySelector(".formula-bar output").textContent =
            selected.dataset.letter + (rows().indexOf(selected.parentElement) + 1);
        book.querySelector(".formula-bar span").textContent =
            selected.dataset.formula || cellValue(selected);
    }

    function select(cell, focus = true) {
        if (!cell) return;
        if (selected && selected !== cell) {
            selected.classList.remove("selected", "editing");
            selected.tabIndex = -1;
            selected.removeAttribute("aria-selected");
        }
        selected = cell;
        cell.tabIndex = 0;
        cell.classList.add("selected");
        cell.setAttribute("aria-selected", "true");
        formulaBar();
        if (focus) {
            cell.focus({preventScroll: true});
            cell.scrollIntoView({block: "nearest", inline: "nearest"});
        }
    }

    function editing(cell, initial) {
        const input = editor(cell);
        if (!input) return status("Esta celda no se puede editar.", true);
        select(cell);
        beforeEdit = input.value;
        cell.classList.add("editing");
        input.focus();
        if (initial !== undefined) input.value = initial;
        else if (input.type === "text") input.select();
        formulaBar();
    }

    function move(key, reverse = false) {
        const allRows = rows();
        const row = selected.parentElement;
        const r = allRows.indexOf(row);
        const c = cells(row).indexOf(selected);
        const width = cells(row).length;
        let nextRow = r;
        let nextCol = c;
        if (key === "ArrowUp") nextRow -= 1;
        if (key === "ArrowDown") nextRow += 1;
        if (key === "ArrowLeft") nextCol -= 1;
        if (key === "ArrowRight") nextCol += 1;
        if (key === "Home") nextCol = 0;
        if (key === "End") nextCol = width - 1;
        if (key === "Tab") {
            nextCol += reverse ? -1 : 1;
            if (nextCol < 0) { nextRow -= 1; nextCol = width - 1; }
            if (nextCol >= width) { nextRow += 1; nextCol = 0; }
        }
        const target = allRows[nextRow] && cells(allRows[nextRow])[nextCol];
        if (!target && key === "Tab") return false;
        select(target || selected);
        selected.classList.remove("editing");
        return true;
    }

    async function mutate(url, data) {
        const response = await fetch(url, {method: "POST", body: data, headers: {Accept: "application/json"}});
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "No se pudo guardar la fila.");
        return result.records;
    }

    function draftRows(exclude) {
        const drafts = new Map();
        for (const row of rows()) {
            const form = rowForm(row);
            const id = row.dataset.record;
            if (!form || exclude.has(id)) continue;
            const previous = originals.get(id);
            const current = values(form);
            if (previous && String(previous) !== String(current)) {
                drafts.set(row.matches(".append-row") ? "new" : id, current);
            }
        }
        return drafts;
    }

    async function refresh(drafts, target, letter) {
        const url = new URL(location.href);
        url.hash = "";
        url.searchParams.delete("guardado");
        const response = await fetch(url);
        if (!response.ok) throw new Error("Guardado. Recarga la hoja para ver los cambios.");
        const doc = new DOMParser().parseFromString(await response.text(), "text/html");
        const next = doc.querySelector(".workbook");
        if (!next || next.dataset.week !== book.dataset.week) {
            throw new Error("Guardado. Recarga la hoja para actualizar la semana o la sesión.");
        }
        const oldScroll = book.querySelector(".grid-scroll");
        const offset = [oldScroll.scrollLeft, oldScroll.scrollTop];
        for (const selector of ["[data-sheet-summary]", ".report-section .sheet-tabs"]) {
            const target = document.querySelector(selector);
            const updated = doc.querySelector(selector);
            if (target && updated) target.replaceWith(updated);
        }
        book.replaceWith(next);
        bind(next);
        const scroll = next.querySelector(".grid-scroll");
        [scroll.scrollLeft, scroll.scrollTop] = offset;
        for (const row of rows()) {
            const draft = drafts.get(row.matches(".append-row") ? "new" : row.dataset.record);
            if (!draft) continue;
            for (const cell of cells(row)) {
                const input = editor(cell);
                if (input && draft.has(input.name)) input.value = draft.get(input.name);
            }
        }
        const targetRow = rows().find((row) => row.dataset.record === target) || rows().at(-1);
        const targetCell = targetRow?.querySelector(".grid-" + letter);
        if (targetCell) select(targetCell);
        return doc;
    }

    const stamp = () => new Intl.DateTimeFormat("es-DO", {
        hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "America/Santo_Domingo"
    }).format(new Date());

    async function save(row, form, letter, descend = false) {
        if (busy) return;
        const payload = values(form);
        const id = row.dataset.record;
        const append = row.matches(".append-row");
        const old = originals.get(id);
        const target = descend ? row.nextElementSibling?.dataset.record : id;
        const drafts = draftRows(new Set([id]));
        if (form.action.endsWith("/edit-production") && String(old) === String(payload)) {
            if (descend) move("ArrowDown");
            else select(selected);
            return;
        }
        busy = true;
        book.setAttribute("aria-busy", "true");
        status("Guardando…");
        let committed = false;
        try {
            const saved = await mutate(form.action, payload);
            committed = true;
            const isDelete = form.action.endsWith("/delete-production");
            undo = isDelete ? null : {saved, previous: append ? null : old};
            await refresh(drafts, append && !descend ? saved[0].id : target, letter);
            status(saved.some((record) => record.state === "pending")
                ? "Guardado · Duplicado pendiente de revisión." : "Guardado · " + stamp());
        } catch (error) {
            status(committed ? error.message : "No se guardó: " + error.message, true);
        } finally {
            busy = false;
            book.removeAttribute("aria-busy");
        }
    }

    async function undoLast() {
        if (busy) return;
        const row = selected?.parentElement;
        const form = rowForm(row);
        const original = row && originals.get(row.dataset.record);
        if (form && original && String(original) !== String(values(form))) {
            for (const cell of cells(row)) {
                const input = editor(cell);
                if (input) input.value = original.get(input.name);
            }
            formulaBar();
            return status("Cambios de la fila cancelados.");
        }
        if (!undo) return status("No hay cambios de esta sesión para deshacer.");
        const revisions = new Map(undo.saved.map((item) => [item.id, item.revision]));
        const current = rows().filter((item) => revisions.has(item.dataset.record));
        if (current.length !== revisions.size || current.some((item) => !rowForm(item))) {
            return status("Quita el filtro de orden para deshacer este cambio.", true);
        }
        const latest = values(rowForm(current[0]));
        const payload = new URLSearchParams(undo.previous || latest);
        payload.set("revision", revisions.get(current[0].dataset.record));
        if (current.length > 1) {
            payload.set("undo_batch", JSON.stringify(current.map((item) => {
                const data = values(rowForm(item));
                return {record: data.get("record"), revision: revisions.get(item.dataset.record)};
            })));
        }
        const drafts = draftRows(new Set(revisions.keys()));
        const letter = selected?.dataset.letter || "B";
        busy = true;
        status("Guardando…");
        try {
            await mutate(undo.previous ? "/edit-production" : "/delete-production", payload);
            const id = undo.previous ? undo.saved[0].id : undefined;
            undo = null;
            await refresh(drafts, id, letter);
            status("Cambio deshecho · " + stamp());
        } catch (error) {
            status(error.message, true);
        } finally {
            busy = false;
        }
    }

    // Google Sheets quotes cells containing tabs, newlines or quotation marks.
    function parseTsv(text) {
        const result = [];
        let row = [];
        let value = "";
        let quoted = false;
        text = text.replace(/\r\n?/g, "\n");
        for (let i = 0; i <= text.length; i++) {
            const char = text[i] ?? "\n";
            if (char === '"' && (quoted || !value)) {
                if (quoted && text[i + 1] === '"') { value += '"'; i++; }
                else quoted = !quoted;
            } else if (!quoted && (char === "\t" || char === "\n")) {
                row.push(value);
                value = "";
                if (char === "\n") {
                    if (row.some((cell) => cell.trim())) result.push(row);
                    row = [];
                }
            } else value += char;
        }
        if (quoted) throw new Error("El texto pegado contiene comillas sin cerrar.");
        return result;
    }

    async function pasteRows(text) {
        const row = book.querySelector(".append-row");
        const form = rowForm(row);
        if (!form) return status("Selecciona un láser de la semana abierta con operarios asignados.", true);
        if (busy) return;
        const defaults = values(form);
        let batch;
        const start = selected?.dataset.letter ?? "A";
        try {
            const parsed = parseTsv(text);
            if (!parsed.length || parsed.length > 200) throw new Error("Pega entre 1 y 200 filas.");
            const columns = {A: "day", B: "order_number", C: "line", D: "pieces",
                E: "comments", I: "sku", L: "employee"};
            const offset = parsed[0][0].match(/^\d{1,4}[-/]\d{1,2}[-/]\d{2,4}$/) ? 0 : start.charCodeAt(0) - 65;
            if (offset > 1) throw new Error("Pega las filas desde la columna A o B.");
            batch = parsed.map((line) => {
                const record = {day: defaults.get("day"), employee: defaults.get("employee")};
                for (let i = 0; i < line.length; i++) {
                    const key = columns[String.fromCharCode(65 + offset + i)];
                    if (key && (line[i] || !["day", "employee"].includes(key))) record[key] = line[i];
                }
                return record;
            });
        } catch (error) {
            return status(error.message, true);
        }
        const signature = JSON.stringify(batch);
        if (failedPaste?.signature === signature) batch = failedPaste.batch;
        else for (const row of batch) {
            row.id = [...crypto.getRandomValues(new Uint8Array(16))]
                .map((octet) => octet.toString(16).padStart(2, "0")).join("");
        }
        const drafts = draftRows(new Set());
        defaults.set("batch", JSON.stringify(batch));
        busy = true;
        status("Guardando…");
        let committed = false;
        try {
            const saved = await mutate(form.action, defaults);
            committed = true;
            failedPaste = null;
            undo = {saved, previous: null};
            await refresh(drafts, undefined, "B");
            const pending = saved.filter((record) => record.state === "pending").length;
            status("Guardado · " + saved.length + " filas" + (pending ? " · " + pending + " por revisar." : "."));
        } catch (error) {
            if (!committed) failedPaste = {signature, batch};
            status(committed ? error.message : "No se guardó el bloque: " + error.message, true);
        } finally {
            busy = false;
        }
    }

    bind(book);
    document.addEventListener("click", (event) => {
        const cell = event.target.closest(".grid-cell");
        if (!cell?.closest(tableSelector) || cell === selected && cell.classList.contains("editing")) return;
        event.preventDefault();
        if (event.pointerType === "touch" && editor(cell)) editing(cell);
        else select(cell);
    });
    document.addEventListener("focusin", (event) => {
        if (event.target.matches(".grid-cell")) select(event.target, false);
    });
    document.addEventListener("dblclick", (event) => {
        const cell = event.target.closest(".grid-cell");
        if (cell?.closest(tableSelector)) editing(cell);
    });
    document.addEventListener("input", (event) => {
        if (event.target.closest(".grid-cell") === selected) formulaBar();
    });
    document.addEventListener("submit", (event) => {
        const row = event.target.closest("tbody tr");
        if (!row || !row.closest(tableSelector)) return;
        event.preventDefault();
        save(row, event.target, selected?.dataset.letter || "B");
    });
    document.addEventListener("keydown", (event) => {
        const cell = event.target.closest(".grid-cell");
        if (!cell?.closest(tableSelector) || event.isComposing) return;
        const {key} = event;
        const modifying = event.ctrlKey || event.metaKey;
        const open = cell.classList.contains("editing");
        if (modifying && key.toLowerCase() === "z" && !open) {
            event.preventDefault();
            undoLast();
        } else if (key === "Enter" && !modifying) {
            event.preventDefault();
            const row = cell.parentElement;
            const form = rowForm(row);
            if (form && form.reportValidity()) save(row, form, cell.dataset.letter, true);
            else if (!form) move("ArrowDown");
        } else if (key === "Escape" && open) {
            event.preventDefault();
            editor(cell).value = beforeEdit;
            cell.classList.remove("editing");
            select(cell);
        } else if (key === "F2") {
            event.preventDefault();
            editing(cell);
        } else if (key === "Tab" || !open && ["Home", "End", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(key)) {
            if (move(key, event.shiftKey)) event.preventDefault();
            else cell.classList.remove("editing");
        } else if (!open && !modifying && !event.altKey && key.length === 1) {
            event.preventDefault();
            const input = editor(cell);
            if (input?.matches("select, input[type=date]")) editing(cell);
            else editing(cell, key);
        }
    });
    document.addEventListener("copy", (event) => {
        const cell = event.target.closest(".grid-cell");
        if (!cell?.closest(tableSelector) || cell.classList.contains("editing")) return;
        event.clipboardData.setData("text/plain", cellValue(cell));
        event.preventDefault();
    });
    document.addEventListener("paste", (event) => {
        const cell = event.target.closest(".grid-cell");
        if (!cell?.closest(tableSelector)) return;
        event.preventDefault();
        if (book.dataset.userRole !== "supervisor") {
            return status("El pegado lo hace el supervisor.", true);
        }
        const text = event.clipboardData.getData("text/plain");
        if (/[\t\r\n]/.test(text.trim())) pasteRows(text);
        else editing(cell, text);
    });
}
