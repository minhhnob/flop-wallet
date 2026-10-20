"""Receipts must verify offline and must catch tampering — and must be honest about what the
status model means. Each test runs against an isolated temp home.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _fresh_home():
    d = tempfile.mkdtemp(prefix="flopwallet-test-")
    os.environ["FLOP_WALLET_HOME"] = d
    return d


def test_good_receipt_verifies():
    _fresh_home()
    from flop_wallet import receipts, signing, store
    s = signing.Signer(bytes(range(32)))
    nonce = "100"
    canonical = signing.canonical_say("lobby", nonce, "hi there")
    sig = s.sign(canonical)
    store.append_receipt(receipts.build(
        "alice", s.did, "say", {"room": "lobby"}, nonce, canonical, sig, "sent",
        {"base": "x", "status": 200, "seq": 1, "confirmed": True}))
    results = receipts.verify_all()
    assert len(results) == 1 and results[0]["ok"], results


def test_tampered_canonical_fails():
    _fresh_home()
    from flop_wallet import receipts, signing, store
    s = signing.Signer(bytes(range(32)))
    canonical = signing.canonical_say("lobby", "100", "hi there")
    sig = s.sign(canonical)
    r = receipts.build("alice", s.did, "say", {"room": "lobby"}, "100", canonical, sig, "sent", {})
    r["canonical"] = "lobby|100|tampered"  # change the text after signing
    store.append_receipt(r)
    results = receipts.verify_all()
    assert not results[0]["ok"]
    assert any("signature" in reason for reason in results[0]["reasons"])


def test_target_mismatch_fails():
    _fresh_home()
    from flop_wallet import receipts, signing, store
    s = signing.Signer(bytes(range(32)))
    canonical = signing.canonical_say("lobby", "100", "hi")
    sig = s.sign(canonical)
    r = receipts.build("alice", s.did, "say", {"room": "other"}, "100", canonical, sig, "sent", {})
    store.append_receipt(r)  # target says 'other' but canonical says 'lobby'
    results = receipts.verify_all()
    assert not results[0]["ok"]
    assert any("canonical string does not match" in x for x in results[0]["reasons"])


def test_nonce_reorder_flagged():
    _fresh_home()
    from flop_wallet import receipts, signing, store
    s = signing.Signer(bytes(range(32)))
    # two DISTINCT writes to one room, second with a lower nonce — a reorder/replay
    for nonce, text in (("200", "first"), ("100", "second")):
        canonical = signing.canonical_say("lobby", nonce, text)
        sig = s.sign(canonical)
        store.append_receipt(
            receipts.build("a", s.did, "say", {"room": "lobby"}, nonce, canonical, sig, "sent", {}))
    results = receipts.verify_all()
    assert results[0]["ok"]  # nonce 200 is fine
    assert not results[1]["ok"] and any("not greater" in x for x in results[1]["reasons"])


def test_pending_and_final_collapse_to_one():
    _fresh_home()
    from flop_wallet import receipts, signing, store
    s = signing.Signer(bytes(range(32)))
    canonical = signing.canonical_say("lobby", "100", "hi")
    sig = s.sign(canonical)
    # one write: a pending record before the call, a final record after it — same id
    store.append_receipt(
        receipts.build("a", s.did, "say", {"room": "lobby"}, "100", canonical, sig, "pending", {}))
    store.append_receipt(
        receipts.build("a", s.did, "say", {"room": "lobby"}, "100", canonical, sig, "sent",
                       {"seq": 7, "confirmed": True}))
    latest = store.latest_receipts()
    assert len(latest) == 1 and latest[0]["status"] == "sent"
    results = receipts.verify_all()
    assert len(results) == 1 and results[0]["ok"]
