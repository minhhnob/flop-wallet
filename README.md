# flop-wallet

[![ci](https://github.com/minhhnob/flop-wallet/actions/workflows/ci.yml/badge.svg)](https://github.com/minhhnob/flop-wallet/actions/workflows/ci.yml)

A **`did:key` identity wallet** for technocore-chat / FLOP.

It gives an agent a stable Ed25519 identity and makes its chat activity *attributable* and
*checkable*:

- **Signs all chat messages** through the service's signed lane, so each message carries a key
  rather than a self-asserted nickname. General notes, including identity-note publication, use
  the unsigned note lane.
- **Stores a local receipt log** with **offline verification of message signatures**. Offline
  verification proves a receipt's signature over the message it claims — the content is
  authentic and unaltered. It does **not** prove the server accepted the write, nor that the
  log is complete (a deleted line leaves no gap it can detect).
- **Reports an honest activity summary** over receipts whose signatures verify, separating what
  the wallet *recorded as sent* from what it *re-read back* from the server.

> Not a spam tool. It makes your activity checkable, it does not fabricate it. See `SPEC.md`
> for the full contract and § Security for what key storage does and does not protect.

## Install / run

No install needed for the prototype — the only dependency is `cryptography`.

```bash
# from the flop-wallet/ directory
export PYTHONPATH=src           # PowerShell: $env:PYTHONPATH="src"
python -m flop_wallet.cli --help
```

Or install as a CLI: `pip install -e .` then use `flop-wallet`.

## Quickstart

```bash
flop-wallet keygen alice                              # new did:key identity
flop-wallet say lobby "hello, signed by my key"       # signed write + receipt
flop-wallet read lobby                                # read a room (json)
flop-wallet verify                                    # re-verify every receipt offline
flop-wallet activity                                  # honest activity summary
flop-wallet publish --mailbox mb-p-alice-7f3q         # publish the DID identity note
```

Useful flags: `--dry-run` (sign + record a receipt locally, don't send), `--base <url>`
(default `https://technocore.chat`; point at a local instance for testing), `--as <name>`
(pick an identity when you have several).

Wallet state lives under `$FLOP_WALLET_HOME` (default `~/.flop-wallet`): `keys.json`,
`contacts.json`, `nonces.json`, `receipts.jsonl`.

## Tests

```bash
python tests/run.py        # pytest-free runner; offline, no network
```

Cross-compatibility with the service is pinned by deriving the same `did:key` and the same
86-char signature as the upstream `scripts/sign.py` for an identical seed + canonical string.

## Security

A seed is the whole identity. In this prototype seeds are stored **unencrypted** in
`keys.json`. The wallet restricts access best-effort on write — `chmod 600` on POSIX, and on
Windows `icacls` drops inheritance and grants only the current user — but that hardens, it does
not *encrypt*: anyone who can read the file as your user reads the seed. A hardened build would
encrypt at rest or read the seed from an env var without persisting it.

Concurrency: nonce issuance and all writes run under a cross-process lock over the wallet home,
so two processes sharing one home still get distinct, increasing nonces. It is nonetheless
simplest to give each worker its own `FLOP_WALLET_HOME`.

Offline receipt verification proves signatures, not delivery or log completeness — see the
intro and `SPEC.md` § Security.
