import pytest

from server.config import settings
from server.db.registry import get_db


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    """Force the in-memory fake DB for every test, regardless of .env."""
    monkeypatch.setattr(settings, "db_provider", "fake")
    get_db.cache_clear()
    yield
    get_db.cache_clear()
