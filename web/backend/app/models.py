#C:\DM\BOT_FS\web\backend\app\models.py
from typing import List, Optional
from pydantic import BaseModel


class TradePart(BaseModel):
    size_usdt: float
    qty: float
    entry_price: float
    exit_price: float
    exit_time_ms: int
    reason: str
    pnl_usdt: float = 0.0
    pnl_percent: float = 0.0


class CompletedTrade(BaseModel):
    id: int
    symbol: str
    timeframe: str
    direction: str
    setup: str

    opened_at_ms: int
    closed_at_ms: Optional[int] = None

    entry_price: float
    size_usdt: float

    tp1_price: float
    tp2_price: float
    sl_price: float

    tp1_hit: bool
    tp2_hit: bool
    sl_hit: bool

    close_reason: Optional[str] = None

    pnl_usdt: float
    pnl_percent: float

    parts: List[TradePart]

    @property
    def duration_minutes(self) -> float:
        if not self.closed_at_ms:
            return 0
        return (self.closed_at_ms - self.opened_at_ms) / 60000

    @property
    def is_win(self) -> bool:
        return self.pnl_usdt > 0

    @property
    def is_loss(self) -> bool:
        return self.pnl_usdt < 0

    @property
    def is_breakeven(self) -> bool:
        return abs(self.pnl_usdt) < 1e-6


# ====== API RESPONSE MODELS ======

class StatsResponse(BaseModel):
    total_trades: int
    winrate: float
    expectancy: float
    avg_pnl: float


class EquityPoint(BaseModel):
    index: int
    trade_id: int
    cumulative_pnl: float


class EquityResponse(BaseModel):
    setup: Optional[str]
    points: List[EquityPoint]


class SetupsResponse(BaseModel):
    setups: List[str]


class SetupStats(BaseModel):
    setup: str
    total_trades: int

    tp1_tp2_count: int
    tp1_sl_count: int
    sl_only_count: int

    profit_tp1_tp2_usdt: float
    profit_tp1_sl_usdt: float
    loss_sl_usdt: float

    profitable_trades_percent: float
    losing_trades_percent: float

    avg_profit_tp1_only_usdt: float
    avg_profit_tp1_tp2_usdt: float
    avg_loss_sl_only_usdt: float


class SetupAnalyticsResponse(BaseModel):
    items: List[SetupStats]


class SetupSymbolStats(BaseModel):
    setup: str
    symbol: str
    total_trades: int

    tp1_tp2_count: int
    tp1_sl_count: int
    sl_only_count: int

    profit_tp1_tp2_usdt: float
    profit_tp1_sl_usdt: float
    loss_sl_usdt: float

    profitable_trades_percent: float
    losing_trades_percent: float

    avg_profit_tp1_only_usdt: float
    avg_profit_tp1_tp2_usdt: float
    avg_loss_sl_only_usdt: float


class SetupSymbolAnalyticsResponse(BaseModel):
    items: List[SetupSymbolStats]
