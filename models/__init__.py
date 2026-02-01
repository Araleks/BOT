from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Candle:
    """
    Универсальное представление закрытой свечи,
    с которой работают все сетапы и менеджер.
    """
    symbol: str
    timeframe: str
    t_close_ms: int
    o: float
    h: float
    l: float
    c: float


@dataclass
class Signal:
    """
    Универсальный сигнал от сетапа.
    Никакой логики Telegram, сделок и т.п. — только факт сигнала.
    """
    symbol: str
    timeframe: str
    t_close_ms: int
    setup: str
    direction: str  # 'bull', 'bear', 'neutral' и т.п.
    extra: Dict[str, Any] = field(default_factory=dict)
