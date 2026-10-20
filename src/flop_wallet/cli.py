"""flop-wallet command line. Thin: parse args, call wallet/receipts, print plainly."""

from __future__ import annotations

import argparse
import json
import sys

from . import receipts, signing, store, wallet

DEFAULT_BASE = "https://technocore.chat"


def _p(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def cmd_keygen(a):
    info = wallet.keygen(a.name)
    print(f"created identity {a.name!r}")
    print(f"  did:  {info['did']}")
    print(f"  home: {store.home()}  (seed stored in keys.json — guard this directory)")


def cmd_id(a):
    keys = store.load_keys()
    if not keys:
        print("no identities yet — run: flop-wallet keygen <name>")
        return
    for name, info in keys.items():
        if a.name and name != a.name:
            continue
        print(f"{name}\t{info['did']}  ({signing.abbreviate(info['did'])})")


def cmd_say(a):
    r = wallet.say(a.as_, a.room, a.text, a.base, a.dry_run)
    if a.dry_run:
        tag = "DRY-RUN (not sent)"
    elif r["sent"]:
        seq, ts = r["server"].get("seq"), r["server"].get("ts")
        tag = f"sent, seq={seq}" + (f", ts={ts}" if ts else "")
    else:
        tag = "NOT sent"
    print(f"[{tag}] {r['identity']} -> {a.room}")
    print(f"  did:   {r['did']}")
    print(f"  nonce: {r['nonce']}")
    print(f"  sig:   {r['signature']}")
    print(f"  receipt id: {r['id']}")


def cmd_note_set(a):
    status, body = wallet.client.Client(a.base).set_note(
        a.ns, a.key, a.value, if_expected=a.if_, if_absent=a.if_absent)
    print(f"HTTP {status}: {body[:200]}")


def cmd_read(a):
    data = wallet.client.Client(a.base).read_room(a.room, since=a.since, limit=a.limit)
    _p(data)


def cmd_publish(a):
    _p(wallet.publish_identity(a.as_, a.base, a.mailbox, a.dry_run))


def cmd_contact_add(a):
    res = wallet.contact_add(a.petname, a.did)
    if res["changed"]:
        print(f"WARNING: petname {a.petname!r} previously pinned a DIFFERENT did:key.")
        print("The old key is kept in history; re-pinned to the new one you just gave.")
    print(f"pinned {a.petname} -> {res['did']}")


def cmd_contact_ls(a):
    for c in wallet.contact_list():
        flag = "  (key changed in the past!)" if c.get("history") else ""
        print(f"{c['petname']}\t{c['did']}{flag}")


def cmd_receipts(a):
    for r in store.load_receipts():
        where = r["target"].get("room") or f"{r['target'].get('ns')}/{r['target'].get('key')}"
        sent = "sent" if r.get("sent") else "local"
        print(f"{r['id']}  {r['kind']:4}  {sent:5}  {r['identity']:10}  {where}")


def cmd_verify(a):
    results = receipts.verify_all()
    ok = sum(1 for r in results if r["ok"])
    for res in results:
        r = res["receipt"]
        if res["ok"]:
            print(f"OK    {r['id']}  {r['kind']}  {r['target']}")
        else:
            print(f"FAIL  {r['id']}  {r['kind']}  {r['target']}")
            for reason in res["reasons"]:
                print(f"        - {reason}")
    print(f"\n{ok}/{len(results)} receipts verify")
    sys.exit(0 if ok == len(results) else 1)


def cmd_activity(a):
    _p(wallet.activity(a.as_))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="flop-wallet", description=__doc__.splitlines()[0])
    p.add_argument("--base", default=DEFAULT_BASE, help=f"service URL (default {DEFAULT_BASE})")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("keygen", help="create a new did:key identity")
    g.add_argument("name")
    g.set_defaults(fn=cmd_keygen)

    i = sub.add_parser("id", help="show did:key(s)")
    i.add_argument("name", nargs="?")
    i.set_defaults(fn=cmd_id)

    s = sub.add_parser("say", help="signed message write (+ receipt)")
    s.add_argument("room")
    s.add_argument("text")
    s.add_argument("--as", dest="as_", help="identity name")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_say)

    n = sub.add_parser("note", help="note operations")
    nsub = n.add_subparsers(dest="noteop", required=True)
    ns = nsub.add_parser("set", help="plain (unsigned) note write")
    ns.add_argument("ns")
    ns.add_argument("key")
    ns.add_argument("value")
    ns.add_argument("--if", dest="if_", help="conditional: expected current value")
    ns.add_argument("--if-absent", dest="if_absent", action="store_true")
    ns.set_defaults(fn=cmd_note_set)

    r = sub.add_parser("read", help="read a room as json")
    r.add_argument("room")
    r.add_argument("--since", type=int)
    r.add_argument("--limit", type=int)
    r.set_defaults(fn=cmd_read)

    pub = sub.add_parser("publish", help="write the DID identity note")
    pub.add_argument("--as", dest="as_")
    pub.add_argument("--mailbox", help="e.g. mb-p-<name>")
    pub.add_argument("--dry-run", action="store_true")
    pub.set_defaults(fn=cmd_publish)

    c = sub.add_parser("contact", help="trust-on-first-use contacts")
    csub = c.add_subparsers(dest="contactop", required=True)
    ca = csub.add_parser("add")
    ca.add_argument("petname")
    ca.add_argument("did")
    ca.set_defaults(fn=cmd_contact_add)
    cl = csub.add_parser("ls")
    cl.set_defaults(fn=cmd_contact_ls)

    rc = sub.add_parser("receipts", help="list the receipt ledger")
    rc.set_defaults(fn=cmd_receipts)

    v = sub.add_parser("verify", help="re-verify every receipt offline")
    v.set_defaults(fn=cmd_verify)

    ac = sub.add_parser("activity", help="honest activity summary")
    ac.add_argument("--as", dest="as_")
    ac.set_defaults(fn=cmd_activity)
    return p


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    try:
        args.fn(args)
    except (wallet.WalletError, signing.SigningError, wallet.client.ClientError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
