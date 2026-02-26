# signal_formatter.py
from datetime import datetime
from zoneinfo import ZoneInfo

from shared.models import Signal

def format_signal(signal: Signal, tz: str) -> str:
    """
    Формирует красивое Telegram‑сообщение.
    """

    # Иконка направления
    if signal.direction in ("bull", "oversold"):
        icon = "🟢"
    elif signal.direction in ("bear", "overbought"):
        icon = "🔴"
    else:
        icon = "⚪"

    # Время закрытия свечи
    dt_close = datetime.fromtimestamp(signal.t_close_ms / 1000, ZoneInfo(tz))
    candle_close_str = dt_close.strftime("%H:%M")

    # Время открытия свечи (если есть в extra)
    open_str = signal.extra.get("open_str")
    close_str = signal.extra.get("close_str")

    if open_str and close_str:
        candle_range = f"{open_str.split(' ')[1]}–{close_str.split(' ')[1]}"
    else:
        # fallback: просто время закрытия
        candle_range = candle_close_str

    # Время сигнала
    now = datetime.now(ZoneInfo(tz))
    signal_time = now.strftime("%H:%M %d.%m.%Y")

    # Формируем текст
    text = (
        f"<b>{icon} {signal.setup}</b>\n"
        f"<b>Таймфрейм:</b> {signal.timeframe}\n"
        f"<b>Пара:</b> {signal.symbol}\n"
        f"<b>Свеча:</b> {candle_range}\n"
        f"<b>Сигнал:</b> {signal_time}"
    )

    return text
