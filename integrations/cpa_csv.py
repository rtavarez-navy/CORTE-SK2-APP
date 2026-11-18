"""Adapter temporal: carga de CSV exportado AUTORIZADO de CPA.

No es conexión en vivo. Si el export no existe o está obsoleto, el backend bloquea registros.
"""
import csv
from pathlib import Path
from decimal import Decimal, InvalidOperation
from sqlalchemy.orm import Session


def normalize_order(value: str) -> str:
    import re
    raw = str(value or "").strip().upper()
    if raw.startswith("SO-"):
        raw = raw[3:]
    if not re.fullmatch(r"[0-9]{4,20}", raw):
        raise ValueError(f"Número de orden inválido: {value!r}")
    return raw


def normalize_line(value: str) -> str:
    import re
    raw = str(value or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{1,5}", raw):
        raise ValueError(f"Línea inválida: {value!r}")
    return raw


def pieces_from_cpa(value: str) -> int:
    try:
        d = Decimal(str(value).strip())
        if not d.is_finite() or d != d.to_integral_value() or d < 0:
            raise ValueError("Cantidad CPA debe ser un entero no negativo")
        return int(d)
    except (InvalidOperation, TypeError):
        raise ValueError(f"Cantidad CPA inválida: {value!r}")


def read_csv(source: Path) -> tuple[dict[tuple[str, str], int], int]:
    """Columnas observadas: 'SO #', 'Set', 'Qty'. Devuelve (registros, filas sin Set)."""
    with source.open("r", encoding="utf-8-sig", newline="") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = "excel"
        rows = csv.DictReader(fh, dialect=dialect)
        if not rows.fieldnames:
            raise ValueError("Archivo CPA sin encabezados")
        required = {"SO #", "Set", "Qty"}
        if not required.issubset(set(rows.fieldnames)):
            raise ValueError(f"Columnas requeridas: {', '.join(sorted(required))}")
        results: dict[tuple[str, str], int] = {}
        skipped = 0
        for row_no, row in enumerate(rows, start=2):
            if not any((str(v or "").strip() for v in row.values())):
                continue
            if not str(row["Set"] or "").strip():
                skipped += 1
                continue
            try:
                key = (normalize_order(row["SO #"]), normalize_line(row["Set"]))
                pieces = pieces_from_cpa(row["Qty"])
                if key in results and results[key] != pieces:
                    raise ValueError(f"Líneas CPA inconsistentes: {key}")
                results[key] = pieces
            except ValueError as e:
                raise ValueError(f"Fila CSV {row_no}: {e}") from e
        if not results:
            raise ValueError("CSV sin órdenes válidas")
        return results, skipped


def import_csv(db: Session, source: Path) -> dict:
    """CSV provisional; usa el mismo contrato que usará la fuente web autorizada."""
    from integrations.cpa_source import CPALimit, sync_cpa_source

    records, skipped = read_csv(source)

    class CSVSource:
        def fetch_limits(self):
            return (CPALimit(order, line, maximum)
                    for (order, line), maximum in records.items())

    count = sync_cpa_source(db, CSVSource())
    return {"importadas": count, "filas_sin_set_omitidas": skipped,
            "fuente": str(source), "nota": "Solo se actualizan las órdenes del CSV"}
