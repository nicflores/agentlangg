import json
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from server.logging import get_logger

logger = get_logger("trace")


def _serialize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_serialize(item) for item in value]
    return value


def trace_event(event: str, **fields: Any) -> None:
    logger.info(json.dumps({"event": event, **_serialize(fields)}, default=str))
