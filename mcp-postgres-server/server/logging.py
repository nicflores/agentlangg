import logging

from server.config import settings


def get_logger(name: str = "mcp-postgres") -> logging.Logger:
    root = logging.getLogger("mcp-postgres")

    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(handler)
        root.setLevel(settings.app_log_level.upper())
        root.propagate = False

    if name == "mcp-postgres":
        return root

    return logging.getLogger(f"mcp-postgres.{name}")
