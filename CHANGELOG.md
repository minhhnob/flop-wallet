# Changelog

All notable changes to flop-wallet are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versioning is [SemVer](https://semver.org/).

## [0.1.0] - 2026-10-20

First prototype.

### Added
- `did:key` (Ed25519) identity management: `keygen`, `id`.
- Signed **chat message** writes via the service's `say-signed` lane, with automatic POST
  fallback when the GET URL would exceed the edge URL budget. General notes (including the
  identity note via `publish`) use the plain, unsigned note lane, matching the protocol.
- Delivery status on every message receipt (`dry-run` / `pending` / `sent` / `rejected` /
  `unknown`): the attempt is recorded *before* the network call, and a network error records
  `unknown` rather than losing the record. The pending and final rows share one id and collapse
  to a single row (`store.latest_receipts`).
- Read-after-write: a `sent` message is read back and its receipt stamped with the
  server-assigned `seq`/`ts` (`server.confirmed`), matched by the record's unique signature
  (best-effort — a busy or ephemeral room degrades to unconfirmed rather than erroring).
- Strictly-increasing, persisted nonces per (identity, target), issued under a cross-process
  advisory lock (`.wallet.lock`); per-process temp files for atomic writes.
- Best-effort at-rest key hardening: `chmod 600`/`700`, and on Windows `icacls` to drop
  inheritance and grant only the current user.
- Local receipt log (`receipts.jsonl`) with offline signature verification (`verify`):
  signature, canonical/structured-field match, and monotonic-nonce checks. Verification proves
  authorship of the content; it does not prove server acceptance or log completeness.
- Trust-on-first-use contacts (`contact add` / `contact ls`) that flag key changes.
- DID identity-note publishing (`publish`), optionally carrying a mailbox.
- Honest activity summary (`activity`): positive metrics gated on signature verification, and
  locally-recorded sends (`recorded_sent`) separated from server-confirmed ones
  (`server_confirmed`).
- Pytest-free test runner (`tests/run.py`); signing proven byte-for-byte compatible with the
  upstream `scripts/sign.py`.

### Known limitations
- Seeds are stored **unencrypted** in `keys.json`; file permissions harden but do not encrypt
  (see SPEC.md § Security).
- Receipt server metadata (`status`, `seq`, `ts`) is the wallet's own account, not covered by
  the signature; the append-only log can be truncated without detection.
- Concurrent use is correct via the home lock but not optimized; prefer one
  `FLOP_WALLET_HOME` per worker.
