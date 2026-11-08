"""Immutable run records (rule 7). The only thing the job ever writes.

Records are created exclusively ('x') and made read-only; a rerun creates a new file.
Nothing here touches the ledger.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from .models import Config, Line, RunResult


def _default(o):
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    raise TypeError(type(o))


def hash_lines(lines: Iterable[Line]) -> str:
    rows = sorted((asdict(l) for l in lines), key=lambda r: (r["id"], r["date"]))
    blob = json.dumps(rows, sort_keys=True, default=_default).encode()
    return hashlib.sha256(blob).hexdigest()


def build_record(ours: list[Line], theirs: list[Line], cfg: Config,
                 result: RunResult, run_at: datetime) -> dict:
    return {
        "run_at": run_at.isoformat(),
        "inputs": {"ours_sha256": hash_lines(ours), "theirs_sha256": hash_lines(theirs),
                   "ours_count": len(ours), "theirs_count": len(theirs)},
        "parameters": json.loads(json.dumps(asdict(cfg), default=_default)),
        "matches": [asdict(m) for m in result.matches],
        "breaks": [asdict(b) for b in result.breaks],
        "metrics": result.metrics,
        "alerts": list(result.alerts),
    }


def write_record(directory: Path, record: dict) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = record["run_at"].replace(":", "").replace("-", "")
    path = directory / f"run_{stamp}_{record['inputs']['ours_sha256'][:8]}.json"
    with open(path, "x", encoding="utf-8") as f:   # 'x': never overwrite
        json.dump(record, f, indent=2, sort_keys=True)
    os.chmod(path, 0o444)
    return path


def load_records(directory: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(directory.glob("run_*.json"))]
