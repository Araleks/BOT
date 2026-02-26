#C:\DM\BOT_FS\web\backend\app\repository.py
import json
from typing import List
from shared.models import CompletedTrade, TradePart
from .config import TRADES_JSON_PATH


def load_trades() -> List[CompletedTrade]:
    if not TRADES_JSON_PATH.exists():
        return []

    with open(TRADES_JSON_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    trades = []
    for item in raw:
        parts = [
            TradePart(
                size_usdt=p["size_usdt"],
                qty=p["qty"],
                entry_price=p["entry_price"],
                exit_price=p["exit_price"],
                exit_time_ms=p["exit_time_ms"],
                reason=p["reason"],
                pnl_usdt=p.get("pnl_usdt", 0.0),
                pnl_percent=p.get("pnl_percent", 0.0),
            )
            for p in item["parts"]
        ]

        trades.append(
            CompletedTrade(
                **{k: v for k, v in item.items() if k != "parts"},
                parts=parts,
            )
        )

    return trades
