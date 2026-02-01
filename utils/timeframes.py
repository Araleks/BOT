# utils/timeframes.py
import ccxt


def tf_seconds(exchange: ccxt.Exchange, timeframe: str) -> int:
    """
    Унифицированная функция перевода таймфрейма в секунды.
    Используется демоном и сетапами.
    """
    return exchange.parse_timeframe(timeframe)
