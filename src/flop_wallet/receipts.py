"""Receipts: the wallet's tamper-evident local record of what each identity did.

A receipt is written for every signed write (even a --dry-run), and it carries everything
needed to re-prove the write offline: the canonical string that was signed, the signature,
and the DID. Verification touches no network — that is the point. This is the artifact that
makes an agent's activity *legible and provable* rather than merely claimed.
"""

from __future__ import annotations

import hashlib
import time

from . import signing, store


def build(identity: str, did: str, kind: str, target: dict, nonce: str, canonical: str,
          signature: str, sent: bool, server: dict | None) -> dict:
    rid = hashlib.sha256((canonical + signature).encode()).hexdigest()[:16]
    return {
        "id": rid,
        "ts_local": time.time(),
        "identity": identity,
        "did": did,
        "kind": kind,
        "target": target,
        "nonce": nonce,
        "canonical": canonical,
        "signature": signature,
        "sent": sent,
        "server": server or {},
    }


def _expected_canonical(r: dict) -> str | None:
    """Recompute the canonical string from the receipt's structured fields, so a tampered
    `canonical` is caught rather than trusted. Uses the stored swept text as-is (it is already
    the swept form), re-joining it under the documented grammar."""
    nonce, target = r["nonce"], r["target"]
    if r["kind"] == "say" and "room" in target:
        body = r["canonical"].split("|", 2)[2:]  # the text, exactly as signed
        if not body:
            return None
        return f"{target['room']}|{nonce}|{body[0]}"
    if r["kind"] == "set" and "ns" in target and "key" in target:
        body = r["canonical"].split("|", 3)[3:]
        if not body:
            return None
        return f"{target['ns']}|{target['key']}|{nonce}|{body[0]}"
    return None


def verify_all() -> list[dict]:
    """Verify every receipt offline. Returns a list of {receipt, ok, reasons}."""
    receipts = store.load_receipts()
    seen_max: dict[str, int] = {}  # (did|target) -> highest nonce seen so far
    results = []
    for r in receipts:
        reasons = []
        expected = _expected_canonical(r)
        if expected is None:
            reasons.append("unrecognized kind/target shape")
        elif expected != r["canonical"]:
            reasons.append("canonical string does not match structured fields")
        if not signing.verify(r["did"], r["signature"], r["canonical"]):
            reasons.append("signature does not verify against did over canonical")
        # Monotonic nonce per (did, target): a replay or reorder shows up here.
        tgt = r["target"].get("room") or f"{r['target'].get('ns')}/{r['target'].get('key')}"
        slot = f"{r['did']}|{tgt}"
        try:
            n = int(r["nonce"])
        except (ValueError, TypeError):
            reasons.append("nonce is not an integer")
            n = None
        if n is not None:
            if slot in seen_max and n <= seen_max[slot]:
                reasons.append(f"nonce {n} not greater than prior {seen_max[slot]} for this target")
            seen_max[slot] = max(seen_max.get(slot, n), n)
        results.append({"receipt": r, "ok": not reasons, "reasons": reasons})
    return results
