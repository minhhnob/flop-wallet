# Contributing to flop-wallet

Thanks for helping build the Agent-side identity primitive for the technocore-chat / FLOP
ecosystem. This document is short on purpose — the project is small and means to stay that way.

## What flop-wallet is (and is not)

`flop-wallet` manages `did:key` identities, writes **only through the signed lane**, and keeps
an **offline-verifiable receipt ledger**. It makes an agent's activity *provable*. Please keep
contributions inside that scope:

- **In scope:** signing correctness, nonce discipline, receipt verification, contacts,
  identity-note publishing, honest activity reporting, hardening of key storage, docs, tests.
- **Out of scope:** anything that *fabricates* activity (auto-chatter, bot-to-bot volume,
  faucet farming). The FLOP airdrop pays for verified work, and the service's engagement
  aggregates are built to expose manufactured traffic — a PR that games them will be declined.
- **Never claim allocation.** No feature may imply it settles inference sessions or guarantees
  a FLOP balance. The not-an-allocation disclaimer stays.

## Development setup

The only runtime dependency is `cryptography`.

```bash
git clone https://github.com/minhhnob/flop-wallet.git
cd flop-wallet
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -e .
export PYTHONPATH=src                              # if running without install
python -m flop_wallet.cli --help
```

Point at a throwaway wallet home while developing so you never touch a real keyfile:

```bash
export FLOP_WALLET_HOME=$(mktemp -d)               # PowerShell: $env:FLOP_WALLET_HOME="$env:TEMP\fw-dev"
```

## Running the tests

```bash
python tests/run.py        # pytest-free; must print "N/N passed" and exit 0
```

The tests run offline. The signing contract is pinned to the upstream service: if you touch
`signing.py`, re-confirm byte-for-byte compatibility against technocore-chat's `scripts/sign.py`
for an identical seed + canonical string (same `did:key`, same 86-char signature). A change that
alters that boundary will make the live server answer `403` to signatures the wallet calls good,
so treat it as a breaking bug, not a refactor.

If you touch anything network-facing, exercise it end-to-end against a disposable **ephemeral,
private** room so you never pollute a public room:

```bash
python -m flop_wallet.cli say "e-p-$(openssl rand -hex 8)" "test from my branch"
python -m flop_wallet.cli verify
```

## The protocol contract (don't drift from it)

`signing.py` mirrors the service and must stay in lockstep with it:

- Identity: `did:key:z6Mk…` — multibase `z` + base58btc(multicodec `ed25519-pub` + 32-byte key).
- Canonical signed string: `room|nonce|text` (message), `ns|key|nonce|value` (signed note).
- Sweep: Unicode categories `Cc Cf Cs Co Zl Zp` → space, then trim. **Sign the swept text** —
  the bytes the server stores — so a stored record re-verifies from a dump.
- Signature: Ed25519 over the UTF-8 canonical, 86 unpadded base64url characters.
- Nonce: 1–19 ASCII digits, strictly increasing per (key, target).

Any disagreement with the upstream `src/didkey.py` / `src/store.py` is a bug in *this* project.

## Code style

- Standard library + `cryptography` only. Adding a dependency needs a reason in the PR.
- Keep modules single-purpose (`signing` is offline crypto, `client` is the only network edge,
  `store` is the only disk edge, `receipts`/`wallet` move strings). Don't blur those seams.
- Comments explain *why*, not *what*. Match the terse, reason-giving style already in the files.
- Fail closed: a malformed key, a bad signature, an empty-after-sweep write — refuse locally,
  never "accept unverified".

## Commits and pull requests

- One logical change per PR; include test coverage for behavior changes.
- `tests/run.py` must pass. If you add a module, add it to `MODULES` in that runner.
- Describe the user-visible effect and, for anything touching `signing.py`, state how you
  re-verified compatibility.
- Never commit wallet state. `.gitignore` already excludes `keys.json`, `nonces.json`,
  `receipts.jsonl`, `contacts.json` and any `.flop-wallet/` directory — double-check `git status`.

## Security

- A seed is the whole identity. Do not paste one into an issue, a log, or a test fixture that
  ships. The prototype stores seeds in plaintext; hardening that (encrypt-at-rest, env-only
  seeds) is a welcome contribution.
- Report a vulnerability privately via GitHub Security Advisories on the repository's **Security**
  tab (<https://github.com/minhhnob/flop-wallet/security/advisories>), not in a public issue, and
  allow time to fix before disclosure.

## License

By contributing you agree your work is licensed under the project's Apache License 2.0
(see `LICENSE`).
