"""API CORTE SK2 APP: validación CPA, advertencia de duplicados y registro atómico."""
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import jwt

from backend.database import get_db
from backend.models import User, Workstation, CPAOrder, Production
from backend.security import verify_password, sign_token, decode_token, hash_workstation_key
from backend.settings import cpa_max_age_hours, business_timezone
from integrations.cpa_csv import normalize_order, normalize_line

app = FastAPI(title="CORTE SK2 API", version="0.1.0", docs_url=None, redoc_url=None)
bearer = HTTPBearer(auto_error=False)


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str


class ProductionIn(BaseModel):
    request_id: UUID
    order_number: str
    line: str
    pieces: int = Field(gt=0, le=1_000_000)
    shift: Literal["T1", "T2"]
    confirm_duplicate: bool = False


def current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
                 db: Annotated[Session, Depends(get_db)]) -> User:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, detail="Inicio de sesión requerido")
    try:
        user_id = decode_token(credentials.credentials)
    except (jwt.InvalidTokenError, ValueError, RuntimeError):
        raise HTTPException(401, detail="Sesión inválida o caducada")
    user = db.get(User, user_id)
    if not user or not user.active:
        raise HTTPException(401, detail="Usuario no autorizado")
    return user


def current_workstation(db: Annotated[Session, Depends(get_db)],
                        key: Annotated[str | None, Header(alias="X-Workstation-Key")] = None) -> Workstation:
    if not key or len(key) < 32:
        raise HTTPException(401, detail="Computadora sin autorización")
    machine = db.scalar(select(Workstation).where(Workstation.key_sha256 == hash_workstation_key(key)))
    if not machine or not machine.active:
        raise HTTPException(401, detail="Computadora no autorizada")
    return machine


def normalize_pair(order: str, line: str) -> tuple[str, str]:
    try:
        return normalize_order(order), normalize_line(line)
    except ValueError as e:
        raise HTTPException(422, detail=str(e)) from e


def verify_cpa_fresh(cpa: CPAOrder) -> None:
    stamp = cpa.imported_at
    if stamp.tzinfo is None:  # Algunos drivers SQLite devuelven datetime sin tz.
        stamp = stamp.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - stamp
    if age > timedelta(hours=cpa_max_age_hours()):
        raise HTTPException(503, detail={"code": "CPA_DESACTUALIZADO",
                                         "message": "Información de CPA vencida: solicitar sincronización"})


def available_cpa(db: Session, order_number: str, line: str, *, lock: bool = False):
    stmt = select(CPAOrder).where(CPAOrder.order_number == order_number, CPAOrder.line == line)
    if lock:
        stmt = stmt.with_for_update()
    cpa = db.scalar(stmt)
    if cpa is None:
        raise HTTPException(404, detail={"code": "ORDEN_NO_EN_CPA",
                                          "message": "Orden y línea no disponibles en CPA"})
    verify_cpa_fresh(cpa)
    totals = db.execute(select(func.coalesce(func.sum(Production.pieces), 0), func.count(Production.id))
                        .where(Production.cpa_order_id == cpa.id)).one()
    produced = int(totals[0])
    count = int(totals[1])
    return cpa, produced, count


@app.get("/health")
def health(db: Annotated[Session, Depends(get_db)]):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "version": "0.1.0"}


@app.post("/auth/login")
def login(data: LoginIn, db: Annotated[Session, Depends(get_db)]):
    user = db.scalar(select(User).where(User.username == data.username.strip().lower()))
    if not user or not user.active or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, detail="Usuario o contraseña incorrectos")
    return {"access_token": sign_token(user.id), "token_type": "bearer", "username": user.username}


@app.get("/workstation")
def workstation(_user: Annotated[User, Depends(current_user)],
                machine: Annotated[Workstation, Depends(current_workstation)]):
    return {"laser_number": machine.laser_number}


@app.get("/orders/{order_number}/{line}")
def order_status(order_number: str, line: str,
                 _user: Annotated[User, Depends(current_user)],
                 _machine: Annotated[Workstation, Depends(current_workstation)],
                 db: Annotated[Session, Depends(get_db)]):
    order, line = normalize_pair(order_number, line)
    cpa, produced, count = available_cpa(db, order, line)
    return {"order_number": order, "line": line, "max_pieces": cpa.max_pieces,
            "produced_pieces": produced, "available_pieces": max(0, cpa.max_pieces - produced),
            "prior_entries": count, "imported_at": cpa.imported_at.isoformat()}


@app.post("/production", status_code=201)
def add_production(data: ProductionIn,
                   user: Annotated[User, Depends(current_user)],
                   machine: Annotated[Workstation, Depends(current_workstation)],
                   db: Annotated[Session, Depends(get_db)]):
    """Bloquea la fila CPA con FOR UPDATE; suma/valida/guarda en esa transacción.

    El bloqueo en PostgreSQL serializa registros de una misma orden/línea entre láseres.
    """
    order, line = normalize_pair(data.order_number, data.line)
    req_id = str(data.request_id)
    try:
        existing = db.scalar(select(Production).where(Production.request_id == req_id))
        if existing is not None:
            same = (existing.user_id == user.id and existing.workstation_id == machine.id
                    and existing.shift == data.shift and existing.pieces == data.pieces
                    and existing.cpa_order.order_number == order
                    and existing.cpa_order.line == line)
            if not same:
                raise HTTPException(409, detail={"code": "ID_REUTILIZADO"})
            # Reintento de la misma operación: no se agrega un registro doble.
            cpa = existing.cpa_order
            total = db.scalar(select(func.coalesce(func.sum(Production.pieces), 0))
                              .where(Production.cpa_order_id == cpa.id)) or 0
            return {"id": existing.id, "replayed": True, "produced_total": int(total),
                    "available_pieces": max(0, cpa.max_pieces - int(total))}

        cpa, produced, prior = available_cpa(db, order, line, lock=True)
        # Puede haber esperado aquí un registro idéntico concurrente.
        just_saved = db.scalar(select(Production).where(Production.request_id == req_id))
        if just_saved is not None:
            if (just_saved.user_id != user.id or just_saved.workstation_id != machine.id
                or just_saved.shift != data.shift or just_saved.pieces != data.pieces
                or just_saved.cpa_order_id != cpa.id):
                raise HTTPException(409, detail={"code": "ID_REUTILIZADO"})
            return {"id": just_saved.id, "replayed": True, "produced_total": produced,
                    "available_pieces": max(0, cpa.max_pieces - produced)}
        if produced + data.pieces > cpa.max_pieces:
            raise HTTPException(409, detail={"code": "EXCESO_CPA", "max_pieces": cpa.max_pieces,
                                             "already_produced": produced,
                                             "available_pieces": max(0, cpa.max_pieces - produced)})
        if prior > 0 and not data.confirm_duplicate:
            raise HTTPException(409, detail={"code": "DUPLICADO_REQUIERE_CONFIRMACION",
                                             "prior_entries": prior, "already_produced": produced,
                                             "available_pieces": cpa.max_pieces - produced})
        record = Production(request_id=req_id, cpa_order_id=cpa.id, user_id=user.id,
                            workstation_id=machine.id, shift=data.shift, pieces=data.pieces,
                            duplicate_confirmed=(prior > 0 and data.confirm_duplicate),
                            business_date=datetime.now(business_timezone()).date())
        db.add(record)
        db.commit()
        return {"id": record.id, "replayed": False, "produced_total": produced + data.pieces,
                "available_pieces": cpa.max_pieces - (produced + data.pieces)}
    except IntegrityError as ex:
        db.rollback()
        # La clave idempotente UNIQUE impide duplicados incluso con reintentos concurrentes.
        saved = db.scalar(select(Production).where(Production.request_id == req_id))
        if (saved and saved.user_id == user.id and saved.workstation_id == machine.id
            and saved.shift == data.shift and saved.pieces == data.pieces
            and saved.cpa_order.order_number == order and saved.cpa_order.line == line):
            total = db.scalar(select(func.coalesce(func.sum(Production.pieces), 0))
                              .where(Production.cpa_order_id == saved.cpa_order_id)) or 0
            return {"id": saved.id, "replayed": True, "produced_total": int(total),
                    "available_pieces": max(0, saved.cpa_order.max_pieces - int(total))}
        raise HTTPException(409, detail={"code": "CONFLICTO_DE_REGISTRO"}) from ex
    except Exception:
        db.rollback()
        raise


@app.get("/summary")
def summary(start: date, end: date,
            _user: Annotated[User, Depends(current_user)],
            _machine: Annotated[Workstation, Depends(current_workstation)],
            db: Annotated[Session, Depends(get_db)]):
    if start > end or (end - start).days > 31:
        raise HTTPException(422, detail="Se permite un rango máximo de 32 días")
    rows = db.execute(select(Production.business_date, Workstation.laser_number, Production.shift,
                             func.sum(Production.pieces))
                      .join(Workstation, Production.workstation_id == Workstation.id)
                      .where(Production.business_date >= start, Production.business_date <= end)
                      .group_by(Production.business_date, Workstation.laser_number, Production.shift)
                      .order_by(Production.business_date, Workstation.laser_number, Production.shift)).all()
    return {"items": [{"date": x[0].isoformat(), "laser_number": x[1], "shift": x[2],
                       "pieces": int(x[3])} for x in rows],
            "grand_total": sum(int(x[3]) for x in rows)}
