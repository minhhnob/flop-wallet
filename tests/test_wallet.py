"""Wallet helpers that must be correct without a network: the read-after-write record match."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from flop_wallet import wallet  # noqa: E402

DID = "did:key:z6MkiYbwC5honA2sxE7XLAyJMDFibLvVg8FgodBX4A4CaUgr"
SIG = "A" * 86


def _msgs():
    return [
        {"seq": 1, "from": DID, "sig": "B" * 86, "ts": "t1"},
        {"seq": 2, "from": DID, "sig": SIG, "ts": "t2"},
        {"seq": 3, "from": "did:key:zOther", "sig": "C" * 86, "ts": "t3"},
    ]


def test_find_record_matches_our_sig_and_did():
    rec = wallet.find_record(_msgs(), DID, SIG)
    assert rec is not None and rec["seq"] == 2 and rec["ts"] == "t2"


def test_find_record_needs_matching_did():
    # same sig but attributed to a different DID -> not ours
    msgs = [{"seq": 9, "from": "did:key:zSomeoneElse", "sig": SIG, "ts": "x"}]
    assert wallet.find_record(msgs, DID, SIG) is None


def test_find_record_absent_returns_none():
    assert wallet.find_record(_msgs(), DID, "Z" * 86) is None


def _fresh_home():
    import os
    import tempfile
    os.environ["FLOP_WALLET_HOME"] = tempfile.mkdtemp(prefix="flopwallet-test-")


def test_activity_gates_on_verification_and_confirmation():
    _fresh_home()
    from flop_wallet import receipts, signing, store
    s = signing.Signer(bytes(range(32)))

    def put(nonce, room, text, status, server, tamper=False):
        canonical = signing.canonical_say(room, nonce, text)
        sig = s.sign(canonical)
        r = receipts.build("me", s.did, "say", {"room": room}, nonce, canonical, sig, status, server)
        if tamper:
            r["canonical"] = f"{room}|{nonce}|changed"  # breaks the signature
        store.append_receipt(r)

    put("10", "a", "one", "sent", {"status": 200, "seq": 1, "ts": "2026-01-01T00:00:00Z",
                                     "confirmed": True})          # verified + confirmed
    put("11", "b", "two", "sent", {"status": 200, "seq": None, "confirmed": False})  # sent, unconfirmed
    put("12", "c", "three", "pending", {})                        # pending, not sent
    put("13", "d", "four", "sent", {"status": 200, "seq": 9, "confirmed": True}, tamper=True)  # unverified

    a = wallet.activity(None)
    assert a["receipts_total"] == 4
    assert a["signatures_verified"] == 3          # the tampered one does not verify
    assert a["recorded_sent"] == 2                # two verified 'sent' (tampered excluded)
    assert a["server_confirmed"] == 1             # only the one with a stamped seq
    assert a["distinct_rooms_confirmed"] == 1     # room 'a' only
    assert a["distinct_active_days_confirmed"] == 1
    assert a["by_status"]["pending"] == 1
