# handlers/log_handler.py
from models import Signal


def log_handler(signal: Signal):
    print(
        f"LOG: {signal.symbol} {signal.timeframe} {signal.setup} "
        f"{signal.direction} @ {signal.t_close_ms}"
    )
