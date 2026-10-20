"""The signing contract must match the service byte-for-byte. These pin the pieces that,
if they drifted, would make the server answer 403 to a signature the wallet called good.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from flop_wallet import signing  # noqa: E402


def test_did_shape_and_roundtrip():
    seed = bytes(range(32))
    did = signing.did_from_seed(seed)
    assert did.startswith("did:key:z6Mk")
    assert len(did[len("did:key:"):]) == 48
    assert signing.is_did(did)
    # the public key parses back to 32 bytes
    assert signing.public_key(did).public_bytes_raw() == \
        signing.Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes_raw()


def test_sign_verify_roundtrip():
    s = signing.Signer(bytes(range(32)))
    canonical = signing.canonical_say("lobby", "123", "hello bob")
    sig = s.sign(canonical)
    assert len(sig) == signing.SIG_CHARS
    assert signing.verify(s.did, sig, canonical)
    # a different canonical does not verify
    assert not signing.verify(s.did, sig, signing.canonical_say("lobby", "124", "hello bob"))


def test_sweep_matches_service_categories():
    # newline (Cc), zero-width joiner (Cf) -> spaces, then trimmed
    assert signing.sweep("a\nb") == "a b"
    assert signing.sweep("x‍y") == "x y"
    assert signing.sweep("  trim me  ") == "trim me"


def test_canonical_signs_swept_text():
    # the signature must cover the SWEPT text, so canonical embeds the swept form
    c = signing.canonical_say("r", "1", "a\nb")
    assert c == "r|1|a b"


def test_empty_after_sweep_refused():
    try:
        signing.canonical_say("r", "1", "\n‍")
    except signing.SigningError:
        return
    raise AssertionError("expected SigningError on empty-after-sweep text")


def test_note_path_sharded():
    did = signing.did_from_seed(bytes(range(32)))
    ns, key = signing.note_path(did)
    assert ns.startswith("did-") and len(ns) == len("did-") + 2
    assert len(key) == 14
