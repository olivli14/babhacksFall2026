# AI-generated with Claude (Anthropic). Review before relying on it.
"""Minimal Supabase REST client: insert/upsert/select via PostgREST.

Secret key comes from the OS keychain (service "supabase", username "secret_key").
"""
import keyring
import requests

SUPABASE_URL = "https://csnpsphfgvgolezwfyme.supabase.co"


class DBError(Exception):
    pass


def _headers(extra=None):
    key = keyring.get_password("supabase", "secret_key")
    if not key:
        raise DBError("Supabase key not in keychain. Run: python -m keyring set supabase secret_key")
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    h.update(extra or {})
    return h


def _check(r):
    if r.status_code >= 300:
        raise DBError(f"{r.status_code} {r.text[:300]}")
    return r.json() if r.text else None


def insert(table, rows):
    """Insert rows; returns the inserted rows."""
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", json=rows, timeout=30,
                      headers=_headers({"Prefer": "return=representation"}))
    return _check(r)


def upsert(table, rows, on_conflict):
    """Insert or update rows matching the on_conflict columns (comma-separated)."""
    if not rows:
        return []
    out = []
    for i in range(0, len(rows), 500):
        r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", params={"on_conflict": on_conflict},
                          json=rows[i:i + 500], timeout=60,
                          headers=_headers({"Prefer": "resolution=merge-duplicates,return=minimal"}))
        _check(r)
    return out


def update(table, match, values):
    params = {k: f"eq.{v}" for k, v in match.items()}
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}", params=params, json=values, timeout=30,
                       headers=_headers({"Prefer": "return=minimal"}))
    return _check(r)


def select(table, **filters):
    params = {"select": "*", **{k: f"eq.{v}" for k, v in filters.items()}}
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", params=params, timeout=30, headers=_headers())
    return _check(r)
