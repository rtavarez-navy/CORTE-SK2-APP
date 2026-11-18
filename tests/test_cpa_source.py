from integrations.cpa_source import CPALimit, sync_cpa_source
from sqlalchemy import select
from backend.models import CPAOrder
from tests.conftest import TestDB
import pytest


def test_cpa_source_contract(env):
    class WebMock:
        def fetch_limits(self):
            return [CPALimit("SO-200001", "b", 31)]

    with TestDB() as db:
        assert sync_cpa_source(db, WebMock()) == 1
        row = db.scalar(select(CPAOrder).where(CPAOrder.order_number == "200001"))
        assert (row.line, row.max_pieces) == ("B", 31)


def test_cpa_source_rejects_empty(env):
    class Empty:
        def fetch_limits(self):
            return []

    with TestDB() as db:
        with pytest.raises(ValueError, match="no devolvió órdenes"):
            sync_cpa_source(db, Empty())
