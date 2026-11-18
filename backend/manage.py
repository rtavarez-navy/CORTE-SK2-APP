"""Operaciones administrativas ejecutadas únicamente en servidor autorizado."""
import argparse
import getpass
import secrets
from pathlib import Path
from sqlalchemy import select

from backend.database import Base, engine, SessionLocal
from backend.models import User, Workstation
from backend.security import hash_password, hash_workstation_key
from integrations.cpa_csv import import_csv


def main():
    parser = argparse.ArgumentParser(description="Administración CORTE SK2 (solo servidor)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    sub.add_parser("add-user").add_argument("username")
    sub.add_parser("add-workstation").add_argument("laser", type=int)
    sub.add_parser("import-cpa").add_argument("path", type=Path)
    args = parser.parse_args()
    if args.command == "init-db":
        Base.metadata.create_all(bind=engine)
        print("Esquema inicial creado. Antes de producción real, usar migraciones controladas.")
        return
    with SessionLocal() as db:
        if args.command == "add-user":
            username = args.username.strip().lower()
            if not username:
                raise ValueError("Nombre de usuario requerido")
            if db.scalar(select(User).where(User.username == username)):
                raise ValueError("Este usuario ya existe")
            pwd = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
            if pwd != getpass.getpass("Repetir contraseña: "):
                raise ValueError("Las contraseñas no coinciden")
            db.add(User(username=username, password_hash=hash_password(pwd)))
            db.commit()
            print("Usuario autorizado creado")
        elif args.command == "add-workstation":
            if not 1 <= args.laser <= 11:
                raise ValueError("El láser debe estar entre 1 y 11")
            if db.scalar(select(Workstation).where(Workstation.laser_number == args.laser)):
                raise ValueError("Ya existe esta computadora; gestionar rotación del token por TI")
            key = secrets.token_urlsafe(40)
            db.add(Workstation(laser_number=args.laser, key_sha256=hash_workstation_key(key)))
            db.commit()
            print(f"Láser {args.laser} creado. Guardar esta clave únicamente en su PC autorizada:")
            print(key)
        elif args.command == "import-cpa":
            print(import_csv(db, args.path))


if __name__ == "__main__":
    main()
