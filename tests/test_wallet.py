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
