# flop-wallet

[![ci](https://github.com/minhhnob/flop-wallet/actions/workflows/ci.yml/badge.svg)](https://github.com/minhhnob/flop-wallet/actions/workflows/ci.yml)

A **`did:key` identity wallet** for technocore-chat / FLOP.

It manages Ed25519 identities, writes **only through the signed lane** (so every action is
attributable to a key), keeps a **tamper-evident local receipt ledger** that verifies offline,
and reports an **honest activity summary**. It is the Agent-side primitive for **verified,
attributable activity** — the opposite of the bot-spam the service's engagement aggregates are
built to expose.

> Not a spam tool. It makes your activity *provable*, it does not *fabricate* it. See
> `SPEC.md` for the full contract.

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
python tests/run.py        # pytest-free runner; 10 tests, no network
```

Cross-compatibility with the service is pinned by deriving the same `did:key` and the same
86-char signature as the upstream `scripts/sign.py` for an identical seed + canonical string.

## Security

Seeds are stored in plaintext in `keys.json` in this prototype — lock the directory down. A
hardened build would encrypt at rest or read the seed from an env var without persisting it.
This is called out, not hidden. See `SPEC.md` § Security.
