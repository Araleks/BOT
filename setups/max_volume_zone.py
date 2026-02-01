# setups/max_volume_zone.py
from datetime import datetime
from zoneinfo import ZoneInfo
from utils.timeframes import tf_seconds
from models import Candle, Signal

class MaxVolumeZoneSetup:
    """
    Адаптер для Max_Volume_Zone под менеджер сетапов.
    Берёт exchange и cfg в конструктор и на каждой свече возвращает Signal.
    """
    name = "MaxVolumeZone"

    def __init__(self, exchange, cfg):
        self.exchange = exchange
        self.cfg = cfg

    def on_candle(self, candle: Candle) -> list[Signal]:
        exchange = self.exchange
        cfg = self.cfg

        symbol = candle.symbol
        timeframe = candle.timeframe
        candle_high = candle.h
        candle_low = candle.l
        candle_close_ts_ms = candle.t_close_ms

        timeframe_sec = tf_seconds(exchange, timeframe)
        if timeframe_sec <= 0:
            return []

        candle_open_ts_ms = candle_close_ts_ms - timeframe_sec * 1000

        tz = ZoneInfo(cfg.tz)
        dt_open = datetime.fromtimestamp(candle_open_ts_ms / 1000, tz)
        dt_close = datetime.fromtimestamp(candle_close_ts_ms / 1000, tz)

        open_str = dt_open.strftime("%Y-%m-%d %H:%M")
        close_str = dt_close.strftime("%Y-%m-%d %H:%M")

        price_range = candle_high - candle_low
        if price_range <= 0:
            return []

        price_step = price_range / 5.0
        timeframe_minutes = timeframe_sec // 60
        minutes_limit = timeframe_minutes + 5

        try:
            raw_minutes = exchange.fetch_ohlcv(
                symbol,
                timeframe="1m",
                since=candle_open_ts_ms,
                limit=minutes_limit,
            )
        except Exception as e:
            print(f"❌ {symbol} {timeframe}: ошибка получения 1m — {e}")
            return []

        if not raw_minutes:
            return []

        zone_volumes = [0.0] * 5

        for row in raw_minutes:
            if len(row) < 6:
                continue

            minute_open_ts_ms, o, h, l, c, vol = row[:6]

            if not (candle_open_ts_ms <= minute_open_ts_ms < candle_close_ts_ms):
                continue

            minute_high = float(h)
            minute_low = float(l)
            mid_price = (minute_high + minute_low) / 2.0

            distance_from_low = mid_price - candle_low
            if distance_from_low < 0 or distance_from_low > price_range:
                continue

            zone_index_from_bottom = int(distance_from_low // price_step)
            if zone_index_from_bottom >= 5:
                zone_index_from_bottom = 4

            zone_index_from_top = 4 - zone_index_from_bottom
            zone_volumes[zone_index_from_top] += float(vol)

        max_volume = max(zone_volumes)
        if max_volume <= 0:
            return []

        max_zone_index = zone_volumes.index(max_volume)
        max_zone_number = max_zone_index + 1

        if max_zone_number == 1:
            direction = "bear"
        elif max_zone_number == 5:
            direction = "bull"
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
                    "open_str": open_str,
                    "close_str": close_str,
                    "max_zone_number": max_zone_number,
                },
            )
        ]
