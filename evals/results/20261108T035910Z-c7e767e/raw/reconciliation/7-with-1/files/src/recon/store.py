"""Immutable run records. The only thing the job writes."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from .models import Config, Line, RunResult


def _default(o):
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    raise TypeError(type(o))


def hash_lines(lines: list[Line]) -> str:
    rows = sorted(json.dumps(asdict(l), default=_default, sort_keys=True) for l in lines)
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()


def save_run(directory: Path, run_at: datetime, ours, theirs, config: Config, result: RunResult) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    record = {
        "run_at": run_at.isoformat(),
        "input_hashes": {"ours": hash_lines(ours), "theirs": hash_lines(theirs)},
        "config": asdict(config),
        "matches": [asdict(m) for m in result.matches],
        "breaks": [asdict(b) for b in result.breaks],
        "metrics": result.metrics,
        "alerts": list(result.alerts),
    }
    path = directory / f"run_{run_at.strftime('%Y%m%dT%H%M%S')}.json"
    with open(path, "x") as f:  # "x": never overwrite an existing run
        json.dump(record, f, default=_default, indent=2, sort_keys=True)
    path.chmod(0o444)
    return path


def load_run(path: Path) -> dict:
    return json.loads(Path(path).read_text())
