#C:\DM\BOT_FS\web\backend\app\services.py
from typing import List, Optional, Dict, Tuple
from .models import (
    CompletedTrade,
    StatsResponse,
    EquityResponse,
    EquityPoint,
    SetupAnalyticsResponse,
    SetupStats,
    SetupSymbolAnalyticsResponse,
    SetupSymbolStats,
)


# -----------------------------
# BASIC STATS
# -----------------------------
def calculate_stats(trades: List[CompletedTrade]) -> StatsResponse:
    total = len(trades)
    if total == 0:
        return StatsResponse(
            total_trades=0,
            winrate=0.0,
            expectancy=0.0,
            avg_pnl=0.0,
        )

    wins = [t for t in trades if t.pnl_usdt > 0]
    losses = [t for t in trades if t.pnl_usdt < 0]

    winrate = len(wins) / total * 100

    avg_win = sum(t.pnl_usdt for t in wins) / len(wins) if wins else 0
    avg_loss = abs(sum(t.pnl_usdt for t in losses)) / len(losses) if losses else 0

    p_win = len(wins) / total
    p_loss = len(losses) / total

    expectancy = p_win * avg_win - p_loss * avg_loss
    avg_pnl = sum(t.pnl_usdt for t in trades) / total

    return StatsResponse(
        total_trades=total,
        winrate=winrate,
        expectancy=expectancy,
        avg_pnl=avg_pnl,
    )


# -----------------------------
# EQUITY CURVE
# -----------------------------
def build_equity(trades: List[CompletedTrade], setup: Optional[str] = None) -> EquityResponse:
    if setup:
        trades = [t for t in trades if t.setup == setup]

    cumulative = 0
    points = []

    for idx, t in enumerate(trades, start=1):
        cumulative += t.pnl_usdt
        points.append(
            EquityPoint(
                index=idx,
                trade_id=t.id,
                cumulative_pnl=cumulative,
            )
        )

    return EquityResponse(setup=setup, points=points)


# -----------------------------
# SETUP LIST
# -----------------------------
def get_setups(trades: List[CompletedTrade]) -> List[str]:
    return sorted({t.setup for t in trades})


# -----------------------------
# INTERNAL HELPERS
# -----------------------------
def _classify_trade_parts(trade: CompletedTrade) -> Tuple[bool, bool, bool]:
    has_tp1 = any(p.reason == "TP1" for p in trade.parts)
    has_tp2 = any(p.reason == "TP2" for p in trade.parts)
    has_sl = any(p.reason == "SL" for p in trade.parts)
    return has_tp1, has_tp2, has_sl

def _calc_part_pnl(trade: CompletedTrade, part) -> float:
    """
    Пересчёт PnL по части сделки (TradePart) на основе направления,
    цены входа, цены выхода и количества.
    """
    qty = part.qty
    entry = part.entry_price
    exit_ = part.exit_price

    if trade.direction == "long":
        return (exit_ - entry) * qty
    else:  # short
        return (entry - exit_) * abs(qty)

def _calc_tp1_profit(trade: CompletedTrade) -> float:
    """
    Считает суммарную прибыль по всем TP1-частям сделки.
    Используется для TP1 + SL, чтобы учитывать только прибыль TP1.
    """
    total = 0.0
    for part in trade.parts:
        if part.reason == "TP1":
            total += _calc_part_pnl(trade, part)
    return total


def _update_aggregates(agg: Dict, trade: CompletedTrade):
    has_tp1, has_tp2, has_sl = _classify_trade_parts(trade)

    agg["total_trades"] += 1

    # Категории
    if has_tp1 and has_tp2:
        agg["tp1_tp2_count"] += 1
        agg["profit_tp1_tp2_usdt"] += trade.pnl_usdt
        agg["tp1_tp2_trades"].append(trade)

    elif has_tp1 and has_sl and not has_tp2:
        agg["tp1_sl_count"] += 1
        # Берём только прибыль от TP1 (50% позиции)
        tp1_profit = _calc_tp1_profit(trade)
        agg["profit_tp1_sl_usdt"] += tp1_profit
        agg["tp1_sl_trades"].append(trade)

    elif has_sl and not has_tp1 and not has_tp2:
        agg["sl_only_count"] += 1
        agg["loss_sl_usdt"] += trade.pnl_usdt
        agg["sl_only_trades"].append(trade)

    # Процент прибыльных
    if has_tp1 or has_tp2:
        agg["profitable_trades_count"] += 1

    # Процент убыточных (SL-only)
    if has_sl and not has_tp1 and not has_tp2:
        agg["losing_trades_count"] += 1

    # Средняя прибыль TP1-only
    if has_tp1 and not has_tp2 and not has_sl:
        agg["tp1_only_trades"].append(trade)


def _build_setup_stats_from_agg(setup: str, agg: Dict) -> SetupStats:
    total = agg["total_trades"] if agg["total_trades"] > 0 else 1

    def _avg(trades_list):
        if not trades_list:
            return 0.0
        return sum(t.pnl_usdt for t in trades_list) / len(trades_list)

    avg_profit_tp1_only = _avg(agg["tp1_only_trades"])
    avg_profit_tp1_tp2 = _avg(agg["tp1_tp2_trades"])
    avg_loss_sl_only = _avg(agg["sl_only_trades"])

    profitable_percent = agg["profitable_trades_count"] / total * 100
    losing_percent = agg["losing_trades_count"] / total * 100

    return SetupStats(
        setup=setup,
        total_trades=agg["total_trades"],
        tp1_tp2_count=agg["tp1_tp2_count"],
        tp1_sl_count=agg["tp1_sl_count"],
        sl_only_count=agg["sl_only_count"],
        profit_tp1_tp2_usdt=agg["profit_tp1_tp2_usdt"],
        profit_tp1_sl_usdt=agg["profit_tp1_sl_usdt"],
        loss_sl_usdt=agg["loss_sl_usdt"],
        profitable_trades_percent=profitable_percent,
        losing_trades_percent=losing_percent,
        avg_profit_tp1_only_usdt=avg_profit_tp1_only,
        avg_profit_tp1_tp2_usdt=avg_profit_tp1_tp2,
        avg_loss_sl_only_usdt=avg_loss_sl_only,
    )


# -----------------------------
# SETUP ANALYTICS
# -----------------------------
def calculate_setup_analytics(trades: List[CompletedTrade]) -> SetupAnalyticsResponse:
    print(f"Loaded {len(trades)} trades for setup analytics")

    by_setup: Dict[str, Dict] = {}

    for t in trades:
        print(f"Processing trade {t.id} with setup={t.setup}, symbol={t.symbol}")

        if t.setup not in by_setup:
            by_setup[t.setup] = {
                "total_trades": 0,
                "tp1_tp2_count": 0,
                "tp1_sl_count": 0,
                "sl_only_count": 0,
                "profit_tp1_tp2_usdt": 0.0,
                "profit_tp1_sl_usdt": 0.0,
                "loss_sl_usdt": 0.0,
                "profitable_trades_count": 0,
                "losing_trades_count": 0,
                "tp1_only_trades": [],
                "tp1_tp2_trades": [],
                "sl_only_trades": [],
                "tp1_sl_trades": [],
            }

        _update_aggregates(by_setup[t.setup], t)

    items = [
        _build_setup_stats_from_agg(setup, agg)
        for setup, agg in sorted(by_setup.items(), key=lambda x: x[0])
    ]

    return SetupAnalyticsResponse(items=items)


# -----------------------------
# SETUP + SYMBOL ANALYTICS
# -----------------------------
def calculate_setup_symbol_analytics(trades: List[CompletedTrade]) -> SetupSymbolAnalyticsResponse:
    print(f"Loaded {len(trades)} trades for setup-symbol analytics")

    by_key: Dict[Tuple[str, str], Dict] = {}

    for t in trades:
        key = (t.setup, t.symbol)

        if key not in by_key:
            by_key[key] = {
                "total_trades": 0,
                "tp1_tp2_count": 0,
                "tp1_sl_count": 0,
                "sl_only_count": 0,
                "profit_tp1_tp2_usdt": 0.0,
                "profit_tp1_sl_usdt": 0.0,
                "loss_sl_usdt": 0.0,
                "profitable_trades_count": 0,
                "losing_trades_count": 0,
                "tp1_only_trades": [],
                "tp1_tp2_trades": [],
                "sl_only_trades": [],
                "tp1_sl_trades": [],
            }

        _update_aggregates(by_key[key], t)

    items = []
    for (setup, symbol), agg in sorted(by_key.items(), key=lambda x: (x[0][0], x[0][1])):
        print(f"Building SetupSymbolStats for setup={setup}, symbol={symbol}")

        stats = _build_setup_stats_from_agg(setup, agg)

        items.append(
            SetupSymbolStats(
                setup=setup,
                symbol=symbol,
                total_trades=stats.total_trades,
                tp1_tp2_count=stats.tp1_tp2_count,
                tp1_sl_count=stats.tp1_sl_count,
                sl_only_count=stats.sl_only_count,
                profit_tp1_tp2_usdt=stats.profit_tp1_tp2_usdt,
                profit_tp1_sl_usdt=stats.profit_tp1_sl_usdt,
                loss_sl_usdt=stats.loss_sl_usdt,
                profitable_trades_percent=stats.profitable_trades_percent,
                losing_trades_percent=stats.losing_trades_percent,
                avg_profit_tp1_only_usdt=stats.avg_profit_tp1_only_usdt,
                avg_profit_tp1_tp2_usdt=stats.avg_profit_tp1_tp2_usdt,
                avg_loss_sl_only_usdt=stats.avg_loss_sl_only_usdt,
            )
        )

    return SetupSymbolAnalyticsResponse(items=items)
