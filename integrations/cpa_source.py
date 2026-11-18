"""Contrato desacoplado para futuras fuentes CPA.

La app desktop y los endpoints NO conocen cómo se obtienen las órdenes de CPA.
Un futuro conector autorizado a la web solo necesita implementar `fetch_limits()`
y llamar a `sync_cpa_source()` desde una tarea del servidor.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Protocol
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.models import CPAOrder, Production
from integrations.cpa_csv import normalize_order, normalize_line, pieces_from_cpa


@dataclass(frozen=True)
class CPALimit:
    order_number: str
    line: str
    pieces: int


class CPASource(Protocol):
    """Fuente CPA autorizada. No implementar login en el cliente Windows."""

    def fetch_limits(self) -> Iterable[CPALimit]:
        """Devolver todas las órdenes y líneas para actualizar, sin escribir en DB."""
        ...


def sync_cpa_source(db: Session, source: CPASource) -> int:
    """Persistir límites de forma atómica, rechazando retrocesos inferiores a lo producido.

    PostgreSQL serializa por orden/línea con `FOR UPDATE`; para una integración
    real, la tarea de sincronización se ejecutará en backend, nunca en el cliente.
    """
    count = 0
    seen: dict[tuple[str, str], int] = {}
    now = datetime.now(timezone.utc)
    try:
        for entry in source.fetch_limits():
            order = normalize_order(entry.order_number)
            line = normalize_line(entry.line)
            maximum = pieces_from_cpa(entry.pieces)
            key = (order, line)
            if key in seen:
                if seen[key] != maximum:
                    raise ValueError(f"CPA inconsistente para {order}/{line}")
                continue
            seen[key] = maximum
            cpa = db.scalar(select(CPAOrder).where(CPAOrder.order_number == order,
                            CPAOrder.line == line).with_for_update())
            if cpa is None:
                db.add(CPAOrder(order_number=order, line=line,
                                max_pieces=maximum, imported_at=now))
            else:
                registered = db.scalar(select(func.coalesce(func.sum(Production.pieces), 0))
                                       .where(Production.cpa_order_id == cpa.id)) or 0
                if registered > maximum:
                    raise ValueError(f"CPA {order}/{line} bajó a {maximum}; ya hay {registered} piezas")
                cpa.max_pieces = maximum
                cpa.imported_at = now
            count += 1
        if count == 0:
            raise ValueError("La fuente CPA no devolvió órdenes válidas")
        db.commit()
    except Exception:
        db.rollback()
        raise
    return count
