#web/backend/app/config.py
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

TRADES_JSON_PATH = DATA_DIR / "trades.json"
