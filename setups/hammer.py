# setups/hammer.py
def is_hammer(o: float, h: float, l: float, c: float) -> bool:
    """
    Зеркальная логика Falling Star:
    - маленькое тело
    - длинная нижняя тень
    - короткая верхняя тень
    """
    range_hl = max(h - l, 1e-12)
    body = abs(o - c)
    upper_shadow = h - max(o, c)
    lower_shadow = min(o, c) - l

    return (
        body <= 0.3 * range_hl and
        lower_shadow >= 0.6 * range_hl and
        upper_shadow <= 0.15 * range_hl
    )

from models import Candle, Signal

class HammerSetup:
    """
    Адаптер для менеджера сетапов.
    Использует is_hammer, возвращает Signal без Telegram.
    """
    name = "Hammer"

    def on_candle(self, candle: Candle) -> list[Signal]:
        if is_hammer(candle.o, candle.h, candle.l, candle.c):
            return [
                Signal(
                    symbol=candle.symbol,
                    timeframe=candle.timeframe,
                    t_close_ms=candle.t_close_ms,
                    setup=self.name,
                    direction="bull",  # молот — бычий сигнал
                    extra={},
                )
            ]
        return []
