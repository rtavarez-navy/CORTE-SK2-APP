import os
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["AUTH_SECRET"] = "solo_para_pruebas_123456789012345678901234567890"
os.environ["CPA_MAX_AGE_HOURS"] = "24"

from backend.api import app
from backend.database import Base, get_db
from backend.models import User, Workstation, CPAOrder
from backend.security import hash_password, hash_workstation_key

engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestDB = sessionmaker(bind=engine, expire_on_commit=False)


def test_db_override():
    with TestDB() as db:
        yield db


app.dependency_overrides[get_db] = test_db_override


@pytest.fixture
def env():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestDB() as db:
        db.add(User(username="operador", password_hash=hash_password("PasswordDemo123!")))
        db.add(Workstation(laser_number=1, key_sha256=hash_workstation_key("P"*48)))
        db.add(Workstation(laser_number=2, key_sha256=hash_workstation_key("Q"*48)))
        db.add(CPAOrder(order_number="100001", line="A", max_pieces=20,
                        imported_at=datetime.now(timezone.utc)))
        db.commit()
    with TestClient(app) as client:
        response = client.post("/auth/login", json={"username": "operador", "password": "PasswordDemo123!"})
        assert response.status_code == 200, response.text
        bearer = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {bearer}", "X-Workstation-Key": "P"*48}
        yield client, headers
