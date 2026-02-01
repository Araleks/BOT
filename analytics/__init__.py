# analytics/__init__.py

from web.backend.app.models import CompletedTrade
from .stats import print_stats_for_trades
from .csv_export import export_trades_to_csv
from .equity import plot_equity_curve_for_trades

__all__ = [
    "print_stats_for_trades",
    "export_trades_to_csv",
    "plot_equity_curve_for_trades",
]
