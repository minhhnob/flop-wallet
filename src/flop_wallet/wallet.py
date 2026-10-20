"""High-level wallet operations: create identities, send signed writes, publish identity,
manage contacts, and report an honest activity summary.

Ties together signing (offline), store (on-disk home), client (network) and receipts.
"""

from __future__ import annotations

import secrets
import time

from . import client, receipts, signing, store


class WalletError(RuntimeError):
    pass


# --- identities -------------------------------------------------------------

def keygen(name: str) -> dict:
    keys = store.load_keys()
    if name in keys:
        raise WalletError(f"identity {name!r} already exists")
    seed = secrets.token_hex(32)
    did = signing.did_from_seed(bytes.fromhex(seed))
    keys[name] = {"seed": seed, "did": did, "created": time.time()}
    store.save_keys(keys)
    return keys[name]


def signer_for(name: str | None) -> tuple[str, signing.Signer]:
    """The (name, Signer) for an identity. With no name, the sole identity; errors if
    there are zero or several, because signing the wrong key is not a thing to guess at."""
    keys = store.load_keys()
    if not keys:
        raise WalletError("no identities yet — run: flop-wallet keygen <name>")
    if name is None:
        if len(keys) != 1:
            raise WalletError(f"several identities exist; pass --as <name> ({', '.join(keys)})")
        name = next(iter(keys))
    if name not in keys:
        raise WalletError(f"no identity named {name!r}")
    return name, signing.Signer(bytes.fromhex(keys[name]["seed"]))


# --- signed writes ----------------------------------------------------------

def _parse_seq(body: str) -> int | None:
    # A say-signed reply echoes the stored tail; find the largest `"seq": N` if present.
    import re
    seqs = [int(m) for m in re.findall(r'"seq"\s*:\s*(\d+)', body)]
    return max(seqs) if seqs else None


def find_record(messages: list[dict], did: str, sig: str) -> dict | None:
    """The stored record matching our write, identified by its (unique) signature and DID.

    Pure and newest-first: the signature is 86 base64url characters, so a match is our write,
    not a coincidence. Kept separate from the network so it is testable offline.
    """
    for m in reversed(messages):
        if m.get("sig") == sig and m.get("from") == did:
            return m
    return None


def _stamp_from_server(base: str, room: str, did: str, sig: str) -> tuple[int | None, str | None]:
    """Read the room back and return the server-assigned (seq, ts) for our just-written record.

    Best-effort: the write already succeeded, so a failed or stale read never fails the call —
    it just leaves seq/ts unstamped. A busy room can push our record past the read window, and
    an `e-` record can expire; both degrade to (None, None) rather than erroring.
    """
    try:
        data = client.Client(base).read_room(room, limit=200)
    except client.ClientError:
        return None, None
    record = find_record(data.get("messages", []), did, sig)
    if record is None:
        return None, None
    return record.get("seq"), record.get("ts")


def say(name: str | None, room: str, text: str, base: str, dry_run: bool) -> dict:
    ident, signer = signer_for(name)
    nonce = store.next_nonce(signer.did, room)
    canonical = signing.canonical_say(room, nonce, text)
    sig = signer.sign(canonical)
    target = {"room": room}

    def record(status, server):
        r = receipts.build(ident, signer.did, "say", target, nonce, canonical, sig, status, server)
        store.append_receipt(r)
        return r

    if dry_run:
        return record("dry-run", None)

    # Record the attempt BEFORE the network call. If the process dies or the network throws
    # mid-send, the ledger still shows a write was begun with this nonce. The pending record
    # shares its id with the final one, so they collapse to a single row (store.latest_receipts).
    record("pending", {"base": base})

    try:
        status, body = client.Client(base).say_signed(room, signer.did, sig, nonce, text)
    except client.ClientError as e:
        # No response came back: the write may or may not have landed. 'unknown', not 'failed'.
        record("unknown", {"base": base, "error": str(e)})
        raise WalletError(f"network error — delivery unknown, nonce {nonce} spent: {e}") from None

    ok = 200 <= status < 300
    seq = ts = None
    if ok:
        seq, ts = _parse_seq(body), None
        if seq is None:
            # The signed reply is a text view with no parseable seq, so read the room back and
            # stamp the authoritative seq/ts the server assigned our record.
            seq, ts = _stamp_from_server(base, room, signer.did, sig)
    server = {"base": base, "status": status, "seq": seq, "ts": ts,
              "confirmed": bool(ok and seq is not None),
              "echo": body.strip().splitlines()[-1][:200] if body.strip() else ""}
    r = record("sent" if ok else "rejected", server)
    if not ok:
        raise WalletError(f"server refused: HTTP {status}: {body[:200]}")
    return r


def publish_identity(name: str | None, base: str, mailbox: str | None, dry_run: bool) -> dict:
    """Write the DID identity note so peers can find this key (and optionally its mailbox).

    The identity note lives at /kv/did-<xx>/<rest> (patterns.md §3) and is a plain,
    world-writable note. We write a minimal, self-describing body.
    """
    ident, signer = signer_for(name)
    ns, key = signing.note_path(signer.did)
    body = f"did: {signer.did}"
    if mailbox:
        body += f" mailbox: {mailbox}"
    result = {"identity": ident, "did": signer.did, "note": f"/kv/{ns}/{key}", "body": body}
    if not dry_run:
        status, resp = client.Client(base).set_note(ns, key, body)
        result["status"] = status
        if status != 200:
            raise WalletError(f"server refused: HTTP {status}: {resp[:200]}")
    return result


# --- contacts (trust-on-first-use) -----------------------------------------

def contact_add(petname: str, did: str) -> dict:
    if not signing.is_did(did):
        raise WalletError(f"not a valid did:key: {did!r}")
    contacts = store.load_contacts()
    prior = contacts.get(petname)
    changed = prior is not None and prior["did"] != did
    history = (prior or {}).get("history", [])
    if prior and prior["did"] != did:
        history = history + [{"did": prior["did"], "replaced_at": time.time()}]
    contacts[petname] = {"did": did, "pinned_at": time.time(), "history": history}
    store.save_contacts(contacts)
    return {"petname": petname, "did": did, "changed": changed}


def contact_list() -> list[dict]:
    return [{"petname": p, **c} for p, c in store.load_contacts().items()]


# --- activity summary -------------------------------------------------------

def activity(name: str | None) -> dict:
    """An honest view of activity for one or all identities.

    Every positive metric is gated on the signature verifying offline — an unverified receipt
    counts toward nothing but its own status tally. It also separates what the wallet *recorded
    as sent* (a local 2xx) from what it *confirmed by reading back* from the server (a stamped
    `seq`), because only the latter is evidence the write is actually in the room. Distinct
    rooms and active days are computed from confirmed sends, dated by the server's timestamp
    when present rather than the local clock. It is an activity summary, nothing more.
    """
    results = receipts.verify_all()
    dids = None
    if name is not None:
        keys = store.load_keys()
        if name not in keys:
            raise WalletError(f"no identity named {name!r}")
        dids = {keys[name]["did"]}

    total = verified = sent = confirmed = 0
    by_status: dict[str, int] = {}
    room_set: set[str] = set()
    day_set: set[str] = set()
    for res in results:
        r = res["receipt"]
        if dids is not None and r["did"] not in dids:
            continue
        total += 1
        by_status[r.get("status", "?")] = by_status.get(r.get("status", "?"), 0) + 1
        if not res["ok"]:
            continue  # signature did not verify — excluded from every positive metric
        verified += 1
        server = r.get("server") or {}
        if r.get("status") == "sent":
            sent += 1
            if server.get("seq") is not None:
                confirmed += 1
                if r["kind"] == "say":
                    room_set.add(r["target"].get("room", ""))
                    ts = server.get("ts")
                    day = ts[:10] if isinstance(ts, str) and len(ts) >= 10 else \
                        time.strftime("%Y-%m-%d", time.gmtime(r["ts_local"]))
                    day_set.add(day)
    return {
        "identity": name or "(all)",
        "receipts_total": total,
        "signatures_verified": verified,
        "recorded_sent": sent,            # local 2xx — the wallet's own account
        "server_confirmed": confirmed,    # re-read back from the room (stamped seq)
        "by_status": by_status,           # includes pending / unknown / rejected / dry-run
        "distinct_rooms_confirmed": len(room_set - {""}),
        "distinct_active_days_confirmed": len(day_set),
        "note": (
            "technocore.chat activity only, and the wallet's own account of it. "
            "'server_confirmed' is the subset re-read back from the room; 'recorded_sent' is a "
            "local status that does not by itself prove storage. Not a score, ranking, or "
            "promise of anything, and the local log may be incomplete."
        ),
    }
