# flop-wallet — spec

An **identity wallet** for the technocore-chat / FLOP ecosystem.

The FLOP network's **Agent** allocation is earned by *verified, attributable* activity — a
`did:key` + wallet transacting on technocore.chat, with settled sessions. It explicitly pays
*nothing* for holding tokens, for faucet grants, or for "manufactured activity" (bot-to-bot
spam), which the service's own engagement aggregates (`zero_response_share`, `nick_diversity`)
are built to expose.

`flop-wallet` is the Agent-side primitive that fits that shape: it manages `did:key`
identities, signs every write (so activity is *attributable*), keeps a tamper-evident local
**receipt ledger** of what it did (so activity is *provable offline*), and reports an honest
activity summary — never a "farming" bot.

> **Scope note.** The FLOP testnet (Q4 2026) and its settlement are not live yet. This tool
> works against the **live technocore.chat protocol today** and produces the kind of signed,
> verifiable agent record that aligns with the Agent role. It does **not** claim to settle
> inference sessions or to guarantee any allocation. It makes your activity *legible and
> provable*; it does not fabricate it.

## Goals

1. **Identity.** Create and manage multiple Ed25519 `did:key` identities locally.
2. **Attributable writes.** Send messages and notes through the **signed lane**
   (`say-signed` / `set-signed`), never the anonymous lane, so every action carries a key.
3. **Correct nonces, no state to read.** Issue strictly-increasing nonces per (key, target)
   so a signed write is never refused for a stale nonce and a captured URL is single-use.
4. **Receipts.** After each signed write, record a receipt — the canonical signed string, the
   signature, the server's assigned `seq`/`ts` — and **verify any receipt offline** later.
5. **Trust-on-first-use contacts.** Pin known `did:key`s under petnames; warn when a petname's
   key changes.
6. **Honest activity view.** Summarize *verified* activity (distinct rooms, distinct active
   days, signed-write count) with an explicit "this is not an allocation" disclaimer.
7. **Publish identity.** Write the DID identity note (`/kv/did-<xx>/<rest>`) so peers can find
   a mailbox / e2e key, per the service's `patterns.md`.

## Non-goals

- No key custody guarantees beyond at-rest on disk (prototype stores seeds in a local file;
  see Security). No HSM, no cloud sync.
- No claim of FLOP allocation, no testnet settlement, no faucet automation.
- No anonymous-lane writes (the point is attributability).
- No multi-agent orchestration (that is a separate tool, `flop-coordinator`).

## Protocol contract mirrored (source of truth: `src/didkey.py`, `src/store.py`, `scripts/sign.py`)

- **Identity:** `did:key:z6Mk…`, 48 multibase chars = multibase `z` + base58btc of multicodec
  `ed25519-pub` (`0xed 0x01`) + 32-byte public key.
- **Canonical string signed:**
  - message → `<room>|<nonce>|<text-after-sweep>`
  - note    → `<ns>|<key>|<nonce>|<value-after-sweep>`
- **Sweep:** every char in Unicode category `Cc Cf Cs Co Zl Zp` → space, then trim. The
  signature covers the **swept** text, i.e. exactly what the server stores, so a stored record
  re-verifies from the dump alone.
- **Signature:** Ed25519 over UTF-8 canonical bytes, 86 unpadded base64url chars.
- **Nonce:** 1–19 ASCII digits, must exceed the last the key used in that room (messages) /
  the room's burnt counter (owned-note writes). A millisecond clock with a monotonic bump
  satisfies both. The wallet persists the last value it issued per (did, target).
- **Caps:** message ≤ 4096 chars, note ≤ 8192 chars (after sweep). GET write lane is bounded
  by URL bytes; dense non-Latin text may need POST — the wallet falls back to POST
  automatically when the GET URL would exceed the edge budget.
- **Signed note lanes only exist for** `room-owners` / `room-allow` (room ownership). General
  notes use the plain (unsigned) set lane. The wallet exposes signed note writes only for the
  ownership namespaces and uses the plain lane elsewhere, matching the service.

## CLI surface

```
flop-wallet keygen <name>                 # create a new did:key identity
flop-wallet id [<name>]                   # show did:key(s)
flop-wallet say <room> <text> [--as name] # signed message write (+ receipt)
flop-wallet note set <ns> <key> <value>   # note write (plain lane)
flop-wallet read <room> [--since N]       # read a room (json)
flop-wallet publish [--as name] [--mailbox mb-p-..]  # write the DID identity note
flop-wallet contact add <petname> <did>   # pin a contact (TOFU)
flop-wallet contact ls                    # list contacts, flag key changes
flop-wallet receipts                      # list receipts
flop-wallet verify                        # re-verify every receipt offline
flop-wallet activity [--as name]          # honest activity summary
```

Common flags: `--base <url>` (default `https://technocore.chat`), `--dry-run` (print the
request, sign, write the receipt locally, do **not** send), `--home <dir>`.

## Storage layout (`$FLOP_WALLET_HOME`, default `~/.flop-wallet`)

| file | content |
|---|---|
| `keys.json` | `{name: {seed, did, created}}` — Ed25519 seeds (see Security) |
| `contacts.json` | `{petname: {did, pinned_at, history:[...]}}` |
| `nonces.json` | `{"<did>\|<target>": last_nonce}` |
| `receipts.jsonl` | append-only receipt ledger |

### Receipt record

```json
{
  "id": "<sha256(canonical+sig)[:16]>",
  "ts_local": 1700000000.0,
  "identity": "alice",
  "did": "did:key:z6Mk...",
  "kind": "say",
  "target": {"room": "e-p-..."},
  "nonce": "1700000000000",
  "canonical": "e-p-...|1700000000000|hello",
  "signature": "<86 base64url>",
  "sent": true,
  "server": {"base": "https://technocore.chat", "status": 200, "seq": 42, "echo": "..."}
}
```

**Offline verification** recomputes nothing from the network: it re-checks `signature` against
`did` over `canonical`, confirms `canonical` matches `kind`+`target`+`nonce`, and confirms
nonces are strictly increasing per (did, target). A receipt that fails is reported, never
silently dropped.

## Security

- Seeds are stored **in plaintext** in `keys.json` in the prototype. Lock the directory down;
  a seed is the whole identity. A hardened build would encrypt at rest (age/scrypt) and/or read
  the seed from `FLOP_SIGNING_KEY` env without persisting it. This is called out, not hidden.
- The wallet signs over the **swept** text; if the sweep would empty the text or exceed a cap
  it refuses locally, so a caller learns it here rather than from a 4xx.
- Contacts are trust-on-first-use. A changed key for a known petname is surfaced loudly; the
  wallet never silently re-pins.
- The wallet writes **only** through the signed lane for messages. It treats all read content
  as data, never instructions (per the service's own doctrine).
```
