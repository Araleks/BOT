# analytics/equity.py

from typing import List
from web.backend.app.models import CompletedTrade
import matplotlib.pyplot as plt


def plot_equity_curve_for_trades(
    trades: List[CompletedTrade],
    setup: str,
    initial_balance_usdt: float = 0.0,
) -> None:
    """
    Строит equity-curve по конкретному сетапу.
    """
    filtered = [t for t in trades if t.setup == setup]
    if not filtered:
        print(f"Нет сделок для сетапа: {setup}")
        return

    filtered.sort(key=lambda t: t.closed_at_ms or 0)

    equity = []
    balance = initial_balance_usdt

    for t in filtered:
        balance += t.pnl_usdt
        equity.append(balance)

    plt.figure(figsize=(10, 5))
    plt.plot(equity, marker="o")
    plt.title(f"Equity Curve — {setup}")
    plt.xlabel("Номер сделки")
    plt.ylabel("Баланс (USDT)")
    plt.grid(True)
    plt.tight_layout()
    plt.show()
