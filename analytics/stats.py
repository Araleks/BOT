# analytics/stats.py

from typing import List
from shared.models import CompletedTrade


def print_stats_for_trades(trades: List[CompletedTrade]) -> None:
    if not trades:
        print("Статистика: нет завершённых сделок.")
        return

    # Группируем по сетапам
    by_setup: dict[str, list[CompletedTrade]] = {}
    for t in trades:
        by_setup.setdefault(t.setup, []).append(t)

    print("\n===== СТАТИСТИКА ПО СЕТАПАМ =====")
    for setup, ts in by_setup.items():
        total = len(ts)
        wins = sum(1 for t in ts if t.is_win)
        losses = sum(1 for t in ts if t.is_loss)
        breakevens = sum(1 for t in ts if t.is_breakeven)

        total_pnl = sum(t.pnl_usdt for t in ts)
        avg_pnl = total_pnl / total if total else 0.0

        winrate = wins / total * 100 if total else 0.0

        # Expectancy (упрощённо)
        avg_win = (
            sum(t.pnl_usdt for t in ts if t.is_win) / wins
            if wins
            else 0.0
        )
        avg_loss = (
            abs(sum(t.pnl_usdt for t in ts if t.is_loss)) / losses
            if losses
            else 0.0
        )
        p_win = wins / total if total else 0.0
        p_loss = losses / total if total else 0.0
        expectancy = p_win * avg_win - p_loss * avg_loss

        print(f"\n--- Setup: {setup} ---")
        print(f"Сделок: {total}")
        print(f"Побед: {wins}, Поражений: {losses}, Безубыток: {breakevens}")
        print(f"Winrate: {winrate:.2f}%")
        print(f"Суммарный PnL: {total_pnl:.2f} USDT")
        print(f"Средний PnL: {avg_pnl:.2f} USDT")
        print(f"Expectancy: {expectancy:.2f} USDT/сделка")
