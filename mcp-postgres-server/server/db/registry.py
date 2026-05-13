from functools import lru_cache

from server.config import settings
from server.db.base import DatabaseClient
from server.db.fake import FakePostgresClient
from server.db.real import AsyncpgClient


@lru_cache(maxsize=1)
def get_db() -> DatabaseClient:
    if settings.db_provider == "real":
        return AsyncpgClient()
    return FakePostgresClient()
