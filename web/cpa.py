"""Authorized, read-only lookup through CPA Production Lines."""
import argparse
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from threading import Lock

URL = "https://cp.champrosports.com/lines"
FACTORY = "JuiceSakira2"
SEARCH = "Search by SO #"
COLUMNS = ("SO #", "Set", "Factory", "Qty", "Line Status")
LOGGER = logging.getLogger(__name__)
BROWSER_LOCK = Lock()


class CpaUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Line:
    order: str
    set: str
    quantity: str
    status: str


def split_query(value):
    match = re.fullmatch(r"(?:SO-)?([0-9]{1,24})(?:[ \t]+([A-Z0-9]{1,12}))?",
                         value.strip().upper())
    if not match:
        raise ValueError("Escribe la orden y el Set separados por un espacio. Ejemplo: 3986055 A.")
    return match.groups()


def select_lines(headers, rows, order, requested_set):
    labels = [header.replace("⇅", "").strip() for header in headers]
    if any(labels.count(name) != 1 for name in COLUMNS):
        raise CpaUnavailable("CPA cambió las columnas de Production Lines.")
    indexes = [labels.index(name) for name in COLUMNS]
    result = []
    for row in rows:
        if len(row) <= max(indexes):
            raise CpaUnavailable("CPA devolvió una fila incompleta.")
        number, set_value, factory, qty, status = (row[index].strip() for index in indexes)
        if number.upper().removeprefix("SO-") != order or factory.casefold() != FACTORY.casefold():
            continue
        if requested_set is None or set_value.upper() == requested_set:
            result.append(Line(number, set_value, qty, status))
    return result


def session_state():
    value = os.environ.get("CORTE_CPA_STATE")
    if not value:
        raise CpaUnavailable("La sesión de CPA aún no está configurada en el servidor.")
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise CpaUnavailable("El responsable de CORTE SK2 debe iniciar sesión en CPA desde el servidor.")
    return path


def require_login(page):
    if "/login" in page.url:
        raise CpaUnavailable("La sesión de CPA venció. El responsable debe iniciar sesión de nuevo.")


def select_factory(page):
    button = page.get_by_role("button", name=re.compile(r"(?:factor(?:y|ies) checked|No factories)", re.I))
    button.click(timeout=5000)
    options = page.locator("input[type=checkbox].shadow-none:visible")
    factory_found = False
    for box in options.all():
        label = box.locator("..").inner_text().strip()
        if label == "Check All":
            continue
        selected = label == FACTORY
        if selected:
            factory_found = True
        if box.is_checked() != selected:
            box.set_checked(selected)
    if not factory_found:
        raise CpaUnavailable("La sesión de CPA no tiene disponible la fábrica JuiceSakira2.")
    button.click()


def read_portal(page, order, requested_set):
    page.set_default_timeout(8000)
    page.goto(URL, wait_until="domcontentloaded", timeout=12000)
    require_login(page)
    search = page.get_by_placeholder(SEARCH, exact=True)
    search.or_(page.get_by_role("heading", name="Sign In", exact=True)).first.wait_for()
    require_login(page)
    select_factory(page)
    search.fill(order)
    # The grid uses the same empty text before and after a search. Observe that
    # the search actually loaded before interpreting an empty result.
    grid = page.locator("table").filter(has=page.get_by_label("Filter SO #", exact=True))
    grid.wait_for()
    grid.evaluate("""table => {
        window.corteCpaLoading = false;
        new MutationObserver(records => {
            const loading = records.some(record => [...record.addedNodes].some(
                node => (node.textContent || '').includes('Loading data...')));
            if (loading || table.textContent.includes('Loading data...')) window.corteCpaLoading = true;
        }).observe(table, {subtree: true, childList: true, characterData: true});
    }""")
    page.get_by_role("button", name="SEARCH", exact=True).click()
    page.wait_for_function("""() => {
        const table = document.querySelector('table');
        return location.pathname.includes('/login') || (table &&
            !table.textContent.includes('Loading data...') &&
            (!table.textContent.includes('No records found') || window.corteCpaLoading));
    }""", timeout=15000)
    require_login(page)
    if grid.get_by_text(re.compile(r"^No records found")).count():
        return []
    headers = grid.locator("thead tr").first.locator("th").all_inner_texts()
    if not headers:
        raise CpaUnavailable("CPA no devolvió los encabezados de la consulta.")
    result = []
    pages = page.get_by_text(re.compile(r"^\s*[0-9]+ to [0-9]+ of [0-9]+\s*$"))
    for _ in range(25):
        rows = grid.locator("tbody tr").evaluate_all(
            "rows => rows.map(row => Array.from(row.cells, cell => cell.innerText))")
        result.extend(select_lines(headers, rows, order, requested_set))
        marker = pages.inner_text()
        _, end, total = (int(n) for n in re.findall(r"[0-9]+", marker))
        if end >= total:
            return result
        page.get_by_text("Next", exact=True).click()
        pages.filter(has_not_text=marker).wait_for()
    raise CpaUnavailable("CPA devolvió demasiadas páginas para una sola orden.")


def lookup(value):
    order, requested_set = split_query(value)
    state = session_state()
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError:
        raise CpaUnavailable("Falta instalar Playwright en el servidor de CORTE SK2.") from None
    if not BROWSER_LOCK.acquire(timeout=2):
        raise CpaUnavailable("Hay otra consulta de CPA en curso. Intenta de nuevo en unos segundos.")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, timeout=12000)
            try:
                with browser.new_context(storage_state=str(state)) as session:
                    return read_portal(session.new_page(), order, requested_set)
            finally:
                browser.close()
    except Error:
        LOGGER.warning("CPA lookup failed in browser", exc_info=True)
        raise CpaUnavailable("CPA no respondió a tiempo o cambió su pantalla de búsqueda.") from None
    finally:
        BROWSER_LOCK.release()


def main():
    parser = argparse.ArgumentParser(description="Abrir CPA para iniciar sesión manualmente.")
    parser.parse_args()
    value = os.environ.get("CORTE_CPA_STATE")
    if not value:
        parser.error("Define CORTE_CPA_STATE con la ruta privada del archivo de sesión.")
    from playwright.sync_api import sync_playwright
    path = Path(value).expanduser().resolve()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        with playwright.chromium.launch(headless=False) as browser:
            with browser.new_context() as session:
                page = session.new_page()
                page.goto(URL)
                input("Inicia sesión en el navegador y pulsa Enter cuando CPA muestre Production Lines. ")
                require_login(page)
                page.get_by_placeholder(SEARCH, exact=True).wait_for(timeout=5000)
                payload = session.storage_state(indexed_db=True)
                with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
                    json.dump(payload, temporary)
                try:
                    Path(temporary.name).replace(path)
                finally:
                    Path(temporary.name).unlink(missing_ok=True)
                print("Sesión de CPA lista para CORTE SK2.")


if __name__ == "__main__":
    main()
