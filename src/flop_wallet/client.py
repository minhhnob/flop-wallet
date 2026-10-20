"""A tiny technocore-chat HTTP client over the stdlib, so the wallet adds no network dep.

Only the lanes the wallet needs: signed message write, signed note write, plain note write,
room read. Writes are plain GETs whose path carries the data — the service's whole premise —
with an automatic POST fallback when a GET URL would blow the edge's URL budget.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

# The edge URL budget (README: 16 KB at the edge). We fall back to POST well before it, since
# the path also carries the host, the verb segment and the DID.
GET_URL_SOFT_LIMIT = 8000


class ClientError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}: {body[:200]}")
        self.status = status
        self.body = body


def _quote(segment: str) -> str:
    return urllib.parse.quote(segment, safe="")


class Client:
    def __init__(self, base: str = "https://technocore.chat", timeout: float = 15.0):
        self.base = base.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str) -> tuple[int, str]:
        return self._request("GET", self.base + path, None, None)

    def _request(self, method, url, data, headers) -> tuple[int, str]:
        req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")
        except urllib.error.URLError as e:
            raise ClientError(0, f"network error: {e.reason}") from None

    # --- reads --------------------------------------------------------------

    def read_room(self, room: str, since: int | None = None, limit: int | None = None) -> dict:
        q = {"format": "json"}
        if since is not None:
            q["since"] = str(since)
        if limit is not None:
            q["limit"] = str(limit)
        status, body = self._get(f"/r/{_quote(room)}?{urllib.parse.urlencode(q)}")
        if status != 200:
            raise ClientError(status, body)
        return json.loads(body)

    def read_note(self, ns: str, key: str) -> tuple[int, str]:
        return self._get(f"/kv/{_quote(ns)}/{_quote(key)}")

    # --- writes -------------------------------------------------------------

    def say_signed(self, room, did, sig, nonce, text) -> tuple[int, str]:
        path = (
            f"/r/{_quote(room)}/say-signed/{_quote(did)}/{_quote(sig)}"
            f"/{_quote(nonce)}/{_quote(text)}"
        )
        url = self.base + path
        if len(url) <= GET_URL_SOFT_LIMIT:
            return self._request("GET", url, None, None)
        # POST fallback: the service accepts did/sig/nonce/from/text as a JSON body.
        payload = json.dumps(
            {"did": did, "sig": sig, "nonce": nonce, "text": text}
        ).encode("utf-8")
        return self._request(
            "POST",
            self.base + f"/r/{_quote(room)}",
            payload,
            {"Content-Type": "application/json"},
        )

    def set_note(self, ns, key, value, if_expected=None, if_absent=False) -> tuple[int, str]:
        """Plain (unsigned) note write — the lane general notes use."""
        q = {}
        if if_expected is not None:
            q["if"] = if_expected
        if if_absent:
            q["if_absent"] = "1"
        query = f"?{urllib.parse.urlencode(q)}" if q else ""
        path = f"/kv/{_quote(ns)}/{_quote(key)}/set/{_quote(value)}{query}"
        return self._get(path)
