from dataclasses import dataclass
from typing import List, Callable
from shared.models import Signal


# Тип функции-правила
CompositeRuleFunc = Callable[[List[Signal]], List[Signal]]


@dataclass
class CompositeRule:
    name: str
    func: CompositeRuleFunc
    enabled: bool = True


class CompositeEngine:
    """
    Принимает список сигналов от SetupManager
    и генерирует новые комбинированные сигналы.
    """
    def __init__(self, rules: List[CompositeRule]):
        self.rules = rules

    def process(self, signals: List[Signal]) -> List[Signal]:
        out: List[Signal] = []
        for rule in self.rules:
            if not rule.enabled:
                continue
            try:
                new_signals = rule.func(signals)
                if new_signals:
                    out.extend(new_signals)
            except Exception as e:
                print(f"❌ Ошибка в composite rule {rule.name}: {e}")
        return out
