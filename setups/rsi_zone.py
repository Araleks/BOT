# setups/rsi_zone.py
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List
from utils.timeframes import tf_seconds
from models import Candle, Signal


def compute_rsi(closes: List[float], period: int = 14) -> float | None:
    """
    Расчёт RSI по формуле Wilder (RSI-14).
    """
    if len(closes) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(1, period + 1):
        diff = closes[-i] - closes[-i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(-diff)

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

class RSIZoneSetup:
    """
    Адаптер RSI Zone Entry.
    Работает через compute_rsi и возвращает Signal.
    """
    name = "RSI"

    def __init__(self, exchange, cfg, period: int = 14):
        self.exchange = exchange
        self.cfg = cfg
        self.period = period

    def on_candle(self, candle: Candle) -> list[Signal]:
        exchange = self.exchange
        cfg = self.cfg
        symbol = candle.symbol
        timeframe = candle.timeframe
        candle_close_ts_ms = candle.t_close_ms

        try:
            raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=100)
        except Exception as e:
            print(f"❌ {symbol} {timeframe}: ошибка получения OHLCV для RSI — {e}")
            return []

        if not raw or len(raw) < 15:
            return []

        timeframe_sec = tf_seconds(exchange, timeframe)

        closed_records = []
        for row in raw:
            t_open_ms, o, h, l, c, *_ = row
            t_close_ms = int(t_open_ms) + timeframe_sec * 1000
            if t_close_ms <= candle_close_ts_ms:
                closed_records.append((t_close_ms, o, h, l, c))

        if len(closed_records) < 15:
            return []

        closed_records.sort(key=lambda x: x[0])

        if closed_records[-1][0] != candle_close_ts_ms:
            return []

        closes = [c[4] for c in closed_records]
        rsi = compute_rsi(closes, period=self.period)
        if rsi is None:
            return []

        candle_open_ts_ms = candle_close_ts_ms - timeframe_sec * 1000
        tz = ZoneInfo(cfg.tz)
        open_str = datetime.fromtimestamp(candle_open_ts_ms / 1000, tz).strftime("%Y-%m-%d %H:%M")
        close_str = datetime.fromtimestamp(candle_close_ts_ms / 1000, tz).strftime("%Y-%m-%d %H:%M")

        if rsi <= 20:
            direction = "oversold"
        elif rsi >= 80:
            direction = "overbought"
        else:
            return []

        return [
            Signal(
                symbol=symbol,
                timeframe=timeframe,
                t_close_ms=candle_close_ts_ms,
                setup=self.name,
                direction=direction,
                extra={
                    "rsi": rsi,
                    "open_str": open_str,
                    "close_str": close_str,
                },
            )
        ]
