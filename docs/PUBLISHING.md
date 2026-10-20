# Publishing flop-wallet to GitHub

`flop-wallet` is a self-contained project. These steps turn this folder into its own GitHub
repository and (optionally) list it in `awesome-technocore`.

## 0. Before you push — safety check

Wallet state must never be committed. `.gitignore` already excludes it, but confirm:

```bash
git status --short     # keys.json / nonces.json / receipts.jsonl / contacts.json must NOT appear
```

A seed in `keys.json` is the whole identity. If one ever lands in a commit, treat that identity
as burned: generate a new one and stop using the old key.

## 1. Initialize a fresh repository

Run these from the `flop-wallet/` directory (it currently lives inside the technocore-chat
checkout; a new repo makes it standalone). In this Claude Code session you can prefix a command
with `!` to run it here, e.g. `! git init`.

```bash
cd flop-wallet
git init -b main
git add .
git commit -m "flop-wallet 0.1.0: did:key wallet for technocore-chat"
```

## 2. Create the GitHub repo and push

**With the GitHub CLI** (easiest):

```bash
gh repo create flop-wallet --public --source=. --remote=origin --push \
  --description "did:key identity wallet for technocore-chat / FLOP"
```

**Or manually:** create an empty repo named `flop-wallet` on github.com (no README/license —
this project already has them), then:

```bash
git remote add origin https://github.com/minhhnob/flop-wallet.git
git push -u origin main
```

CI (`.github/workflows/ci.yml`) runs the offline test suite on every push and PR.

## 3. Tag a release (optional)

```bash
git tag -a v0.1.0 -m "flop-wallet 0.1.0"
git push origin v0.1.0
```

Then draft a GitHub Release from the tag, pasting the `0.1.0` section of `CHANGELOG.md`.

## 4. Fill in the placeholders

- URLs, copyright (`LICENSE`/`NOTICE`), and the security contact are already set to the
  `minhhnob` account. Change them only if you publish under a different handle or org.

## 5. List it in awesome-technocore (optional)

[`zunmax/awesome-technocore`](https://github.com/zunmax/awesome-technocore) is the ecosystem
index. To add flop-wallet:

1. Fork the repo and edit its `README.md`.
2. Add one line under **Clients and SDKs** (and/or **Identity, Signing, and Verification**,
   since this is an identity wallet). Keep the list's existing one-line, description-first
   style — see `docs/awesome-entry.md` for the exact snippet to paste.
3. Open a pull request. A good PR description: what the tool does in one sentence, that it is
   signed messages with offline-verified receipts, and that it runs against the live service
   (link your CI badge).

Follow that list's own `CONTRIBUTING` if it has one; match its formatting exactly, as awesome
lists are strict about it.
