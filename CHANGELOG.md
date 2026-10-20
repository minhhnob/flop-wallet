# Changelog

All notable changes to flop-wallet are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versioning is [SemVer](https://semver.org/).

## [0.1.0] - 2026-10-20

First prototype.

### Added
- `did:key` (Ed25519) identity management: `keygen`, `id`.
- Signed message writes via the service's `say-signed` lane, with automatic POST fallback
  when the GET URL would exceed the edge URL budget.
- Read-after-write: each sent message is read back and its receipt stamped with the
  server-assigned `seq` and `ts`, matched by the record's unique signature (best-effort — a
  busy or ephemeral room degrades to unstamped rather than erroring).
- Strictly-increasing, persisted nonces per (identity, target).
- Tamper-evident local receipt ledger (`receipts.jsonl`) and offline verification (`verify`):
  signature, canonical/structured-field match, and monotonic-nonce checks.
- Trust-on-first-use contacts (`contact add` / `contact ls`) that flag key changes.
- DID identity-note publishing (`publish`), optionally carrying a mailbox.
- Honest activity summary (`activity`) with an explicit not-an-allocation disclaimer.
- Pytest-free test runner (`tests/run.py`); signing proven byte-for-byte compatible with the
  upstream `scripts/sign.py`.

### Known limitations
- Seeds are stored in plaintext in `keys.json` (see SPEC.md § Security).
