# signal_router.py
from dataclasses import dataclass
from typing import Callable, List

from models import Signal
from notifier import send_telegram_message


@dataclass
class SignalRouter:
    """
    Централизованный маршрутизатор сигналов.
    Каждый сигнал проходит через все подключённые обработчики.
    """
    handlers: List[Callable[[Signal], None]]

    def route(self, signal: Signal) -> None:
        for handler in self.handlers:
            try:
                handler(signal)
            except Exception as e:
                print(f"❌ Ошибка в обработчике сигналов: {e}")
