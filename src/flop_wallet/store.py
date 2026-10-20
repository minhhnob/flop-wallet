"""The wallet's on-disk home: keys, contacts, nonces, receipts.

All of it is small JSON under one directory ($FLOP_WALLET_HOME, default ~/.flop-wallet).
No database, no daemon — a wallet is files you can read, back up and delete.

Mutations (nonce issuance, saves, receipt appends) run under a single cross-process advisory
lock so a second process sharing the same home cannot interleave a read-modify-write. The lock
makes concurrent use *correct*, not *fast*; it is still simplest to give each worker its own
`FLOP_WALLET_HOME`.
"""

from __future__ import annotations

import contextlib
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

_LOCK_TIMEOUT = 5.0  # seconds to wait for the home lock before giving up


def home() -> Path:
    base = os.environ.get("FLOP_WALLET_HOME")
    path = Path(base) if base else Path.home() / ".flop-wallet"
    created = not path.exists()
    path.mkdir(parents=True, exist_ok=True)
    if created:
        _harden(path, is_dir=True)
    return path


def _harden(path: Path, is_dir: bool) -> None:
    """Best-effort restrict access to the current user. On POSIX this is a real chmod; on
    Windows chmod only toggles the read-only bit, so we also try icacls to drop inheritance
    and grant the owner alone. Both are best-effort — a failure is not fatal, and the README /
    SPEC are honest that this hardens, it does not guarantee, confidentiality."""
    try:
        os.chmod(path, 0o700 if is_dir else 0o600)
    except OSError:
        pass
    if os.name == "nt":
        try:
            import subprocess

            user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
            if user:
                grant = f"{user}:(OI)(CI)F" if is_dir else f"{user}:F"
                subprocess.run(
                    ["icacls", str(path), "/inheritance:r", "/grant:r", grant],
                    capture_output=True, check=False, creationflags=0x08000000,  # CREATE_NO_WINDOW
                )
        except Exception:
            pass


@contextlib.contextmanager
def _lock():
    """A cross-process advisory lock over the whole wallet home. fcntl on POSIX, msvcrt on
    Windows; a dead holder frees it because the OS drops the lock when the handle closes."""
    lock_path = home() / ".wallet.lock"
    fh = open(lock_path, "a+b")
    try:
        fh.seek(0)
        if not fh.read(1):  # the locked region must be a real byte
            fh.write(b"\0")
            fh.flush()
        if os.name == "nt":
            import msvcrt

            deadline = time.monotonic() + _LOCK_TIMEOUT
            while True:
                try:
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise TimeoutError("wallet home is locked by another process") from None
                    time.sleep(0.03)
        else:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fh.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()


def _read_json(name: str, default: Any) -> Any:
    path = home() / name
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(name: str, data: Any, secret: bool = False) -> None:
    # Write-then-replace so a crash never leaves a half-written file. The temp name is unique
    # per process so two writers never share one scratch file.
    path = home() / name
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    if secret:
        _harden(tmp, is_dir=False)  # restrict before it becomes the live file
    tmp.replace(path)
    if secret:
        _harden(path, is_dir=False)


# --- keys -------------------------------------------------------------------

def load_keys() -> dict[str, dict]:
    return _read_json("keys.json", {})


def save_keys(keys: dict[str, dict]) -> None:
    with _lock():
        _write_json("keys.json", keys, secret=True)


# --- contacts ---------------------------------------------------------------

def load_contacts() -> dict[str, dict]:
    return _read_json("contacts.json", {})


def save_contacts(contacts: dict[str, dict]) -> None:
    with _lock():
        _write_json("contacts.json", contacts)


# --- nonces -----------------------------------------------------------------

def load_nonces() -> dict[str, int]:
    return _read_json("nonces.json", {})


def next_nonce(did: str, target: str) -> str:
    """A strictly-increasing nonce for (did, target): a millisecond clock bumped past the last
    value this wallet issued for that pair. The read-modify-write runs under the home lock, so
    two processes sharing a home still get distinct, increasing nonces. Persisted, so a
    captured signed URL stays single-use across restarts."""
    with _lock():
        nonces = load_nonces()
        slot = f"{did}|{target}"
        issued = max(int(time.time() * 1000), nonces.get(slot, 0) + 1)
        nonces[slot] = issued
        _write_json("nonces.json", nonces)
    return str(issued)


# --- receipts ---------------------------------------------------------------

def append_receipt(receipt: dict) -> None:
    with _lock():
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


def latest_receipts() -> list[dict]:
    """One entry per receipt id — the latest status wins — in first-seen order.

    A single write appends a `pending` record before the network call and a final
    `sent`/`rejected`/`unknown` record after it; both carry the same id (the id is a hash of
    the canonical string and signature, which the status does not change), so collapsing by id
    yields one row per write reflecting its final known state."""
    out: dict[str, dict] = {}
    order: list[str] = []
    for r in load_receipts():
        rid = r.get("id")
        if rid not in out:
            order.append(rid)
        out[rid] = r
    return [out[i] for i in order]
