"""Verify sandbox credentials: list subaccounts (master keys), terms status, balances.

Usage: python scripts/check_accounts.py [--accept-terms]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import ACCOUNTS  # noqa: E402
from gemini_auth import GeminiError, private  # noqa: E402


def show(label, fn):
    try:
        print(f"  {label}: {fn()}")
    except GeminiError as e:
        print(f"  {label}: ERROR {e}")


if __name__ == "__main__":
    accept = "--accept-terms" in sys.argv
    if ACCOUNTS["mm"]["key"].startswith("master-"):
        print("Master key detected; accounts in group:")
        show("account/list", lambda: [(a.get("account"), a.get("name"), a.get("type"))
                                      for a in private("mm", "/v1/account/list")])
    for name in ("mm", "shop"):
        print(f"\n[{name}] subaccount={ACCOUNTS[name]['account'] or '(key default)'}")
        show("terms status", lambda: private(name, "/v1/prediction-markets/terms/status", method="GET"))
        if accept:
            show("accept terms", lambda: private(name, "/v1/prediction-markets/terms/accept"))
        show("USD balance", lambda: [b for b in private(name, "/v1/balances") if b.get("currency") == "USD"])
