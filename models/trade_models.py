#C:\DM\BOT_FS\models\trade_models.py
from dataclasses import dataclass, asdict
from typing import List


@dataclass
class TradePart:
    size_usdt: float
    qty: float
    entry_price: float
    exit_price: float
    exit_time_ms: int
    reason: str

    @property
    def pnl_usdt(self) -> float:
        if self.qty == 0:
            return 0.0
        return (self.exit_price - self.entry_price) * self.qty

    @property
    def pnl_percent(self) -> float:
        if self.size_usdt == 0:
            return 0.0
        return (self.pnl_usdt / self.size_usdt) * 100.0

    def to_dict(self) -> dict:
        return {
            "size_usdt": self.size_usdt,
            "qty": self.qty,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "exit_time_ms": self.exit_time_ms,
            "reason": self.reason,
            "pnl_usdt": self.pnl_usdt,
            "pnl_percent": self.pnl_percent,
        }

