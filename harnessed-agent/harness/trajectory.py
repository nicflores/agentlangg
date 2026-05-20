import json
from datetime import datetime, timezone
from pathlib import Path


class TrajectoryLogger:
    def __init__(self, ticker: str):
        Path("./trajectories").mkdir(exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        self.path = f"./trajectories/{ticker}_{ts}.jsonl"

    def log(self, step_type: str, data: dict):
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "step": step_type,
            **data
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(record) + "\n")