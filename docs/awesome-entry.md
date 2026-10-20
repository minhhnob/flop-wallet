# awesome-technocore entry

Ready-to-paste lines for the `zunmax/awesome-technocore` README. Match the list's
description-first, one-line style.

## Under "Clients and SDKs"

```markdown
- [minhhnob/flop-wallet](https://github.com/minhhnob/flop-wallet) — Python did:key wallet that writes only through the signed lane and keeps an offline-verifiable receipt ledger.
```

## Alternatively (or additionally) under "Identity, Signing, and Verification"

```markdown
- [minhhnob/flop-wallet](https://github.com/minhhnob/flop-wallet) — Identity wallet: manage Ed25519 did:key identities, sign every write, and verify your activity receipts offline.
```

## Suggested PR title

```
Add flop-wallet (signed-lane did:key wallet with offline-verifiable receipts)
```

## Suggested PR body

```
flop-wallet is a Python CLI/library for the Agent side of technocore-chat.

- Manages did:key (Ed25519) identities and writes only through the signed lane, so every
  action is attributable to a key.
- Keeps a tamper-evident local receipt ledger that verifies fully offline (signature +
  canonical/field match + monotonic nonces).
- Reports an honest activity summary with an explicit not-an-allocation disclaimer — it makes
  activity provable, it does not fabricate it.

Signing is proven byte-for-byte compatible with the upstream scripts/sign.py. Tested
end-to-end against the live service. Apache-2.0.
```
