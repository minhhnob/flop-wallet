"""The signed-lane client contract, mirrored exactly from the service.

Source of truth: `src/didkey.py` (parse/verify), `src/store.py` clean_text (the sweep),
and `scripts/sign.py` (the canonical strings). This module is the only place in the wallet
that knows cryptography; everything else moves strings around.

Nothing here reaches the network: a did:key *is* its public key, so signing and verifying
are offline, which is the whole reason the signed lane fits a zero-auth service.
"""

from __future__ import annotations

import base64
import hashlib
import unicodedata

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

PREFIX = "did:key:"
MULTICODEC_ED25519 = b"\xed\x01"  # varint ed25519-pub; every z6Mk key decodes from these two
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_INDEX = {c: i for i, c in enumerate(_B58)}

# Mirrored from src/store.py clean_text: categories replaced with a space before storage.
# Kept in step with the service, not imported from it — the wallet runs standalone.
INVISIBLE_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zl", "Zp")

MAX_TEXT_CHARS = 4096  # messages
MAX_VALUE_CHARS = 8192  # notes
MULTIBASE_CHARS = 48
SIG_CHARS = 86


class SigningError(ValueError):
    """The wallet refuses a write before it is sent — empty after sweep, over a cap, bad key."""


def sweep(text: str) -> str:
    """The single-line sweep: invisibles -> spaces, ends trimmed. What the server stores."""
    return "".join(
        " " if unicodedata.category(c) in INVISIBLE_CATEGORIES else c for c in text
    ).strip()


def swept_within(text: str, limit: int) -> str:
    """`sweep(text)`, but raise `SigningError` on exactly what the server would refuse.

    Learning it here, before a signature is minted and a URL is built, beats a 4xx round trip.
    """
    cleaned = sweep(text)
    if not cleaned:
        raise SigningError("nothing visible left after the single-line sweep; nothing to sign")
    if len(cleaned) > limit:
        raise SigningError(f"{len(cleaned)} chars after sweep, over the {limit} cap; split it")
    return cleaned


def _base58_encode(raw: bytes) -> str:
    # The multicodec prefix byte is never zero, so there are no leading-'1' digits to preserve.
    n = int.from_bytes(raw, "big")
    out = ""
    while n:
        n, rem = divmod(n, 58)
        out = _B58[rem] + out
    return out


def _base58_decode(raw: str) -> bytes:
    n = 0
    for ch in raw:
        digit = _B58_INDEX.get(ch)
        if digit is None:
            raise SigningError(f"bad did:key: {ch!r} is not base58btc")
        n = n * 58 + digit
    leading = len(raw) - len(raw.lstrip("1"))
    payload = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\x00" * leading + payload


def public_key(did: str) -> Ed25519PublicKey:
    """The Ed25519 public key inside a did:key, or raise. Mirrors src/didkey.py.public_key."""
    if not isinstance(did, str) or not did.startswith(PREFIX):
        raise SigningError(f"bad did:key: expected {PREFIX}z6Mk...")
    mb = did[len(PREFIX) :]
    if len(mb) != MULTIBASE_CHARS or not mb.startswith("z"):
        raise SigningError(f"bad did:key: expected {MULTIBASE_CHARS} chars starting 'z'")
    decoded = _base58_decode(mb[1:])
    if len(decoded) != 34 or not decoded.startswith(MULTICODEC_ED25519):
        raise SigningError("bad did:key: only ed25519-pub (z6Mk...) keys are accepted")
    return Ed25519PublicKey.from_public_bytes(decoded[2:])


def is_did(value: str) -> bool:
    try:
        public_key(value)
    except SigningError:
        return False
    return True


def abbreviate(did: str) -> str:
    """`z6Mk…2doK` — a full DID is ~56 base58 chars that tokenize badly."""
    mb = did[len(PREFIX) :]
    return f"{mb[:4]}…{mb[-4:]}"


def did_from_seed(seed: bytes) -> str:
    public = Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes_raw()
    return f"{PREFIX}z{_base58_encode(MULTICODEC_ED25519 + public)}"


def canonical_say(room: str, nonce: str, text: str) -> str:
    """`<room>|<nonce>|<swept text>` — the message signature's covered string."""
    return f"{room}|{nonce}|{swept_within(text, MAX_TEXT_CHARS)}"


def canonical_set(ns: str, key: str, nonce: str, value: str) -> str:
    """`<ns>|<key>|<nonce>|<swept value>` — the signed-note signature's covered string."""
    return f"{ns}|{key}|{nonce}|{swept_within(value, MAX_VALUE_CHARS)}"


class Signer:
    """One Ed25519 identity: the did:key it publishes and the signatures it mints."""

    def __init__(self, seed: bytes):
        if len(seed) != 32:
            raise SigningError("a seed is 32 bytes")
        self._key = Ed25519PrivateKey.from_private_bytes(seed)
        self.seed = seed
        self.did = did_from_seed(seed)

    def sign(self, canonical: str) -> str:
        raw = self._key.sign(canonical.encode("utf-8"))
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def verify(did: str, signature: str, canonical: str) -> bool:
    """True iff `signature` is `did`'s Ed25519 signature over `canonical`. Offline, fail-closed."""
    try:
        key = public_key(did)
        if len(signature) != SIG_CHARS:
            return False
        raw = base64.urlsafe_b64decode(signature + "==")
        key.verify(raw, canonical.encode("utf-8"))
    except (SigningError, InvalidSignature, ValueError, TypeError):
        return False
    return True


def note_path(did: str) -> tuple[str, str]:
    """The (namespace, key) a did:key publishes its identity note at (patterns.md §3):
    the first 16 hex of SHA-256(did string), split 2 + 14 so the directory stays sharded."""
    public_key(did)  # refuse to name a path for something that is not a key we accept
    fingerprint = hashlib.sha256(did.encode()).hexdigest()[:16]
    return f"did-{fingerprint[:2]}", fingerprint[2:]
