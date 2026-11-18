from datetime import datetime, timezone
from sqlalchemy import select
import pytest
from integrations.cpa_csv import read_csv, import_csv
from tests.conftest import TestDB
from backend.models import CPAOrder, Production, User, Workstation


def test_sample_csv():
    from pathlib import Path
    path = Path(__file__).parent.parent / "sample-data" / "CPA_EJEMPLO.csv"
    result, skipped = read_csv(path)
    assert result[("100001", "A")] == 20
    assert skipped == 0


def test_import_rejects_lower_limit_with_existing_production(env, tmp_path):
    with TestDB() as db:
        cp = db.scalar(select(CPAOrder).where(CPAOrder.order_number == "100001"))
        user = db.scalar(select(User))
        workstation = db.scalar(select(Workstation).where(Workstation.laser_number == 1))
        db.add(Production(request_id="5a11cda0-5890-4be9-84db-2ad0b27dd870", cpa_order_id=cp.id,
                          user_id=user.id, workstation_id=workstation.id,
                          shift="T1", pieces=12, business_date=datetime.now(timezone.utc).date()))
        db.commit()
        file = tmp_path / "export.csv"
        file.write_text("SO #,Set,Qty\nSO-100001,A,10\n", encoding="utf-8")
        with pytest.raises(ValueError, match="ya hay 12"):
            import_csv(db, file)
        db.refresh(cp)
        assert cp.max_pieces == 20
