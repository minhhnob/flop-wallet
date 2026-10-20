"""The wallet's on-disk home: keys, contacts, nonces, receipts.

All of it is small JSON under one directory ($FLOP_WALLET_HOME, default ~/.flop-wallet).
No database, no daemon — a wallet is files you can read, back up and delete.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def home() -> Path:
    base = os.environ.get("FLOP_WALLET_HOME")
    path = Path(base) if base else Path.home() / ".flop-wallet"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(name: str, default: Any) -> Any:
    path = home() / name
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(name: str, data: Any) -> None:
    # Write-then-replace so a crash never leaves a half-written keyfile.
    path = home() / name
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


# --- keys -------------------------------------------------------------------

def load_keys() -> dict[str, dict]:
    return _read_json("keys.json", {})


def save_keys(keys: dict[str, dict]) -> None:
    _write_json("keys.json", keys)


# --- contacts ---------------------------------------------------------------

def load_contacts() -> dict[str, dict]:
    return _read_json("contacts.json", {})


def save_contacts(contacts: dict[str, dict]) -> None:
    _write_json("contacts.json", contacts)


# --- nonces -----------------------------------------------------------------

def load_nonces() -> dict[str, int]:
    return _read_json("nonces.json", {})


def next_nonce(did: str, target: str) -> str:
    """A strictly-increasing nonce for (did, target): a millisecond clock bumped past the
    last value this wallet issued for that pair. Persisted, so it survives restarts and a
    captured signed URL stays single-use even across processes."""
    nonces = load_nonces()
    slot = f"{did}|{target}"
    issued = max(int(time.time() * 1000), nonces.get(slot, 0) + 1)
    nonces[slot] = issued
    _write_json("nonces.json", nonces)
    return str(issued)


# --- receipts ---------------------------------------------------------------

def append_receipt(receipt: dict) -> None:
    path = home() / "receipts.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, ensure_ascii=False) + "\n")


def load_receipts() -> list[dict]:
    path = home() / "receipts.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out
