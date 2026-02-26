from typing import List
from shared.models import Signal


def _get(signals: List[Signal], name: str) -> List[Signal]:
    return [s for s in signals if s.setup == name]


# 1. FallingStar + VolumeTip
def rule_falling_star_volume(signals: List[Signal]) -> List[Signal]:
    fs = _get(signals, "FallingStar")
    vol = _get(signals, "MaxVolumeZone")
    if fs and vol:
        base = fs[0]
        return [
            Signal(
                symbol=base.symbol,
                timeframe=base.timeframe,
                t_close_ms=base.t_close_ms,
                setup="FallingStar+Volume",
                direction=base.direction,
                extra={"sources": ["FallingStar", "MaxVolumeZone"]},
            )
        ]
    return []


# 2. Hammer + VolumeTip
def rule_hammer_volume(signals: List[Signal]) -> List[Signal]:
    hm = _get(signals, "Hammer")
    vol = _get(signals, "MaxVolumeZone")
    if hm and vol:
        base = hm[0]
        return [
            Signal(
                symbol=base.symbol,
                timeframe=base.timeframe,
                t_close_ms=base.t_close_ms,
                setup="Hammer+Volume",
                direction=base.direction,
                extra={"sources": ["Hammer", "MaxVolumeZone"]},
            )
        ]
    return []


# 3. FallingStar + VolumeTip + RSI
def rule_falling_star_volume_rsi(signals: List[Signal]) -> List[Signal]:
    fs = _get(signals, "FallingStar")
    vol = _get(signals, "MaxVolumeZone")
    rsi = _get(signals, "RSI")
    if fs and vol and rsi:
        base = fs[0]
        return [
            Signal(
                symbol=base.symbol,
                timeframe=base.timeframe,
                t_close_ms=base.t_close_ms,
                setup="FallingStar+Volume+RSI",
                direction=base.direction,
                extra={"sources": ["FallingStar", "MaxVolumeZone", "RSI"]},
            )
        ]
    return []


# 4. Hammer + VolumeTip + RSI
def rule_hammer_volume_rsi(signals: List[Signal]) -> List[Signal]:
    hm = _get(signals, "Hammer")
    vol = _get(signals, "MaxVolumeZone")
    rsi = _get(signals, "RSI")
    if hm and vol and rsi:
        base = hm[0]
        return [
            Signal(
                symbol=base.symbol,
                timeframe=base.timeframe,
                t_close_ms=base.t_close_ms,
                setup="Hammer+Volume+RSI",
                direction=base.direction,
                extra={"sources": ["Hammer", "MaxVolumeZone", "RSI"]},
            )
        ]
    return []


# 5. VolumeTip + RSI
def rule_volume_rsi(signals: List[Signal]) -> List[Signal]:
    vol = _get(signals, "MaxVolumeZone")
    rsi = _get(signals, "RSI")
    if vol and rsi:
        base = vol[0]
        return [
            Signal(
                symbol=base.symbol,
                timeframe=base.timeframe,
                t_close_ms=base.t_close_ms,
                setup="Volume+RSI",
                direction=base.direction,
                extra={"sources": ["MaxVolumeZone", "RSI"]},
            )
        ]
    return []
