# setups/falling_star.py
from models import Candle, Signal

def is_falling_star(o: float, h: float, l: float, c: float) -> bool:
    """
    Упрощённые правила Falling Star:
      - тело мало: |o - c| <= 0.3 * (h - l)
      - верхняя тень большая: (h - max(o, c)) >= 0.6 * (h - l)
      - нижняя тень маленькая: (min(o, c) - l) <= 0.15 * (h - l)
    """
    range_high_low = max(h - l, 1e-12)
    body_size = abs(o - c)
    upper_shadow = h - max(o, c)
    lower_shadow = min(o, c) - l
    return (
        body_size <= 0.3 * range_high_low
        and upper_shadow >= 0.6 * range_high_low
        and lower_shadow <= 0.15 * range_high_low
    )

class FallingStarSetup:
    """
    Адаптер для менеджера сетапов.
    Использует is_falling_star, но не шлёт Telegram — только возвращает Signal.
    """
    name = "FallingStar"

    def on_candle(self, candle: Candle) -> list[Signal]:
        if is_falling_star(candle.o, candle.h, candle.l, candle.c):
            return [
                Signal(
                    symbol=candle.symbol,
                    timeframe=candle.timeframe,
                    t_close_ms=candle.t_close_ms,
                    setup=self.name,
                    direction="bear",   # падающая звезда — медвежий сигнал
                    extra={},
                )
            ]
        return []
