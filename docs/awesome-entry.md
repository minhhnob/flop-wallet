# awesome-technocore entry

Ready-to-paste lines for the `zunmax/awesome-technocore` README. Match the list's
description-first, one-line style.

## Under "Clients and SDKs"

```markdown
- [minhhnob/flop-wallet](https://github.com/minhhnob/flop-wallet) — Python did:key wallet that signs every chat message and keeps a local receipt log with offline signature verification.
```

## Alternatively (or additionally) under "Identity, Signing, and Verification"

```markdown
- [minhhnob/flop-wallet](https://github.com/minhhnob/flop-wallet) — Identity wallet: manage Ed25519 did:key identities, sign every write, and verify your activity receipts offline.
```

## Suggested PR title

```
Add flop-wallet (did:key wallet: signed messages + offline-verified receipt log)
```

## Suggested PR body

```
flop-wallet is a Python CLI/library for the Agent side of technocore-chat.

- Manages did:key (Ed25519) identities and signs every chat message, so each is attributable
  to a key (general notes use the unsigned note lane).
- Keeps a local receipt log with offline signature verification (signature + canonical/field
  match + monotonic nonces). Verification proves authorship, not server acceptance or log
  completeness.
- Reports an honest activity summary over verified receipts, separating locally-recorded sends
  from server-confirmed ones — it makes activity checkable, it does not fabricate it.

Signing is proven byte-for-byte compatible with the upstream scripts/sign.py. Tested
end-to-end against the live service. Apache-2.0.
```
