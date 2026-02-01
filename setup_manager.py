# setup_manager.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol, Iterable

from models import Candle, Signal


class BaseSetup(Protocol):
    """
    Минимальный интерфейс сетапа.
    Каждый сетап принимает закрытую свечу и возвращает 0..N сигналов.
    """
    name: str

    def on_candle(self, candle: Candle) -> List[Signal]:
        ...


@dataclass
class SetupManager:
    """
    Менеджер, который прогоняет свечу через все подключённые сетапы
    и возвращает список сигналов.
    """
    setups: Iterable[BaseSetup]

    def process_candle(self, candle: Candle) -> List[Signal]:
        signals: List[Signal] = []
        for setup in self.setups:
            try:
                setup_signals = setup.on_candle(candle)
                if setup_signals:
                    signals.extend(setup_signals)
            except Exception as e:
                print(f"❌ Ошибка в сетапе {getattr(setup, 'name', setup)}: {e}")
        return signals
