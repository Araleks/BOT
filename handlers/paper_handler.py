# handlers/paper_handler.py
from models import Signal


def paper_handler(signal: Signal):
    print(f"PAPER: обработан сигнал {signal.setup} {signal.symbol}")
