"""Receipts: a local log of what each identity did, with offline verification of signatures.

A receipt carries what is needed to re-check a write offline: the canonical string that was
signed, the signature, and the DID. `verify_all()` re-checks each receipt's signature over its
canonical string and that nonces increase per target.

What this proves and what it does NOT:

* It proves the receipt's signature is this DID's signature over that exact message — the
  content is authentic and unaltered since it was signed.
* It does **not** prove the server accepted or stored the write. That is what the `status`
  field and the server read-back (`server.seq`/`confirmed`) record separately, and even those
  are the wallet's own account, not an independent attestation.
* It does **not** prove the log is complete. The ledger is an append-only file a holder can
  truncate or delete; a removed line leaves no gap this can detect.

A single write appends a `pending` record before the network call and a final record after it
(`sent`, `rejected`, or `unknown`); both share one id, so the ledger reduces to one row per
write (see `store.latest_receipts`).
"""

from __future__ import annotations

import hashlib
import time

from . import signing, store


def build(identity: str, did: str, kind: str, target: dict, nonce: str, canonical: str,
          signature: str, status: str, server: dict | None) -> dict:
    """Build a receipt. `status` is the delivery state this wallet observed:
    `dry-run` | `pending` | `sent` | `rejected` | `unknown`. The id is a hash of the canonical
    string and signature, so the pending and final records of one write collapse together."""
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
        "status": status,
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
    """Verify every receipt offline. Returns a list of {receipt, ok, reasons}.

    Operates on `store.latest_receipts()` — one row per write — so a pending record and its
    final record are checked once, not flagged as a nonce collision with each other.
    """
    receipts = store.latest_receipts()
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
