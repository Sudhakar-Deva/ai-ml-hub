"""Plain-text run log: one line per lap / step, to stdout and a file. The budget
termination log in week7/ is one of these, unedited."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .. import config


def default_path(system: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return config.W7_LOGS_DIR / f"{system}_{ts}.log"


class RunLog:
    def __init__(self, path: Path | None = None, echo: bool = True):
        self.path = path
        self.echo = echo
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, event: str, **fields) -> None:
        stamp = time.strftime("%H:%M:%S")
        extra = "  ".join(
            f"{k}={json.dumps(v) if isinstance(v, (dict, list)) else v}" for k, v in fields.items()
        )
        line = f"{stamp}  {event:<16} {extra}".rstrip()
        if self.echo:
            print(line, flush=True)
        if self.path:
            with self.path.open("a") as f:
                f.write(line + "\n")


NULL = RunLog(None, echo=False)
