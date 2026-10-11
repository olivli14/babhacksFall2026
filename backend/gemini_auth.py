"""Signed private REST calls to Gemini.

Per docs (developer.gemini.com/authentication/api-key): JSON payload with
`request` + `nonce` (+ endpoint fields, + `account` for master keys) is
base64-encoded into X-GEMINI-PAYLOAD; X-GEMINI-SIGNATURE is
hex(HMAC_SHA384(b64_payload, secret)); the HTTP body is empty.
"""
import base64
import hashlib
import hmac
import json
import threading
import time

import requests

from config import ACCOUNTS, SANDBOX_URL

_nonce_lock = threading.Lock()
_last_nonce: dict[str, int] = {}


def _next_nonce(key: str) -> int:
    # Epoch seconds, bumped to stay strictly increasing per key. Valid for both
    # the time-based (+/-30s) and incremental nonce modes.
    with _nonce_lock:
        n = max(int(time.time()), _last_nonce.get(key, 0) + 1)
        _last_nonce[key] = n
        return n


class GeminiError(Exception):
    def __init__(self, status: int, body):
        self.status, self.body = status, body
        super().__init__(f"HTTP {status}: {body}")


def private(account: str, path: str, fields: dict | None = None,
            method: str = "POST", base: str = SANDBOX_URL):
    """Call a private endpoint as agent `account` ("mm" or "shop")."""
    creds = ACCOUNTS[account]
    if not creds["key"] or not creds["secret"]:
        raise RuntimeError(f"No Gemini credentials configured for '{account}'")
    payload = {"request": path, "nonce": _next_nonce(creds["key"]), **(fields or {})}
    if creds["account"]:
        payload["account"] = creds["account"]
    b64 = base64.b64encode(json.dumps(payload).encode())
    sig = hmac.new(creds["secret"].encode(), b64, hashlib.sha384).hexdigest()
    headers = {
        "Content-Type": "text/plain",
        "Content-Length": "0",
        "X-GEMINI-APIKEY": creds["key"],
        "X-GEMINI-PAYLOAD": b64.decode(),
        "X-GEMINI-SIGNATURE": sig,
        "Cache-Control": "no-cache",
    }
    r = requests.request(method, base + path, headers=headers, timeout=15)
    try:
        body = r.json()
    except ValueError:
        body = r.text
    if r.status_code >= 400:
        raise GeminiError(r.status_code, body)
    return body
