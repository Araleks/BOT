# analytics/csv_export.py

import csv
from typing import List
from shared.models import CompletedTrade


def export_trades_to_csv(trades: List[CompletedTrade], path: str) -> None:
    """
    Экспорт завершённых сделок в CSV.
    """
    headers = [
        "id",
        "symbol",
        "timeframe",
        "direction",
        "setup",
        "opened_at_ms",
        "closed_at_ms",
        "duration_minutes",
        "entry_price",
        "size_usdt",
        "sl_price",
        "tp1_price",
        "tp2_price",
        "tp1_hit",
        "tp2_hit",
        "sl_hit",
        "close_reason",
        "pnl_usdt",
        "pnl_percent",
        "parts_count",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for t in trades:
            writer.writerow([
                t.id,
                t.symbol,
                t.timeframe,
                t.direction,
                t.setup,
                t.opened_at_ms,
                t.closed_at_ms,
                t.duration_minutes,
                t.entry_price,
                t.size_usdt,
                t.sl_price,
                t.tp1_price,
                t.tp2_price,
                t.tp1_hit,
                t.tp2_hit,
                t.sl_hit,
                t.close_reason,
                t.pnl_usdt,
                t.pnl_percent,
                len(t.parts),
            ])

    print(f"CSV экспорт завершённых сделок сохранён в: {path}")
