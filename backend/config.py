"""Central config, loaded from backend/.env (locally) or env vars (Railway)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

MODE = os.getenv("MODE", "mock")  # "sandbox" or "mock"
SANDBOX_URL = "https://api.sandbox.gemini.com"
PROD_URL = "https://api.gemini.com"  # public market data only

# Credentials per agent. With a single master key, both agents can share it and
# be separated by subaccount shortname (GEMINI_*_ACCOUNT); leave those blank for
# account-scoped keys.
ACCOUNTS = {
    "mm": {
        "key": os.getenv("GEMINI_MM_API_KEY", ""),
        "secret": os.getenv("GEMINI_MM_API_SECRET", ""),
        "account": os.getenv("GEMINI_MM_ACCOUNT", ""),
    },
    "shop": {
        "key": os.getenv("GEMINI_SHOP_API_KEY") or os.getenv("GEMINI_MM_API_KEY", ""),
        "secret": os.getenv("GEMINI_SHOP_API_SECRET") or os.getenv("GEMINI_MM_API_SECRET", ""),
        "account": os.getenv("GEMINI_SHOP_ACCOUNT", ""),
    },
}
