# handlers/paper_trading.py

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional

from models import Signal, Candle
from web.backend.app.models import TradePart, CompletedTrade

# Импортируем функции аналитики
from analytics.stats import print_stats_for_trades
from analytics.csv_export import export_trades_to_csv
from analytics.equity import plot_equity_curve_for_trades


@dataclass
class Position:
    """
    Открытая бумажная позиция.
    """
    id: int
    symbol: str
    timeframe: str
    direction: str  # 'long' или 'short'
    setup: str
    opened_at_ms: int
    entry_price: float
    size_usdt: float
    qty: float

    sl: float
    tp1: float
    tp2: float

    tp1_hit: bool = False
    closed: bool = False
    closed_at_ms: Optional[int] = None
    parts: List[TradePart] = field(default_factory=list)

    def remaining_qty(self) -> float:
        used = sum(p.qty for p in self.parts)
        return self.qty - used

    def remaining_size_usdt(self) -> float:
        if self.qty == 0:
            return 0.0
        # Пропорционально количеству
        return self.size_usdt * (self.remaining_qty() / self.qty)


class PaperTradingEngine:
    """
    Универсальный движок бумажной торговли.
    - Открывает сделки по сигналам (кроме RSI).
    - Отрабатывает SL/TP по новым свечам.
    - Ведёт историю сделок.
    """

    def __init__(
        self,
        exchange,
        initial_balance_usdt: float = 100_000.0,
        risk_per_trade_usdt: float = 100.0,
        sl_offset_pct: float = 0.001,  # 0.1% от цены свечи
    ):
        self.exchange = exchange
        self.initial_balance_usdt = initial_balance_usdt
        self.risk_per_trade_usdt = risk_per_trade_usdt
        self.sl_offset_pct = sl_offset_pct

        self._next_position_id = 1
        self.open_positions: List[Position] = []
        self.completed_trades: List[CompletedTrade] = []

    # ---------- Публичные методы ----------

    def on_signal(self, signal: Signal):
        """
        Обработка нового сигнала: открытие новой позиции.
        """
        # Не торгуем RSI
        if signal.setup == "RSI":
            return

        # Нас интересуют только направленные сигналы
        if signal.direction not in ("bull", "bear"):
            return

        candle_data = signal.extra.get("candle")
        if not candle_data:
            # Без данных свечи не можем корректно посчитать SL/TP
            print(f"⚠️ Нет данных свечи в signal.extra['candle'] для {signal.symbol} {signal.timeframe}")
            return

        o = float(candle_data["o"])
        h = float(candle_data["h"])
        l = float(candle_data["l"])
        c = float(candle_data["c"])

        # 1. Получаем цену входа по рынку
        entry_price = self._get_entry_price(signal.symbol, signal.direction)
        if entry_price is None:
            print(f"⚠️ Не удалось получить цену входа для {signal.symbol}")
            return

        # 2. Рассчитываем SL от свечи сигнала
        sl = self._calc_stop_loss(signal.direction, h, l)

        # 3. Рассчитываем TP1 и TP2
        tp1, tp2 = self._calc_take_profits(signal.direction, entry_price, sl)

        # 4. Размер позиции: фиксированные 100 USDT
        size_usdt = self.risk_per_trade_usdt
        qty = self._calc_qty(size_usdt, entry_price, signal.direction)

        # 5. Создаём позицию
        pos = Position(
            id=self._next_position_id,
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            direction="long" if signal.direction == "bull" else "short",
            setup=signal.setup,
            opened_at_ms=signal.t_close_ms,
            entry_price=entry_price,
            size_usdt=size_usdt,
            qty=qty,
            sl=sl,
            tp1=tp1,
            tp2=tp2,
        )
        self._next_position_id += 1

        self.open_positions.append(pos)

        print(
            f"PAPER OPEN #{pos.id}: {pos.symbol} {pos.timeframe} {pos.direction} "
            f"entry={pos.entry_price:.4f} sl={pos.sl:.4f} tp1={pos.tp1:.4f} tp2={pos.tp2:.4f} "
            f"size={pos.size_usdt}USDT qty={pos.qty:.6f}"
        )

    def on_candle(self, candle: Candle):
        """
        Обработка новой свечи: проверка SL/TP для всех открытых позиций по этому символу.
        Важно: вызывается на каждой закрытой свече (как и сетапы).
        """
        if not self.open_positions:
            return

        symbol = candle.symbol
        high = candle.h
        low = candle.l
        t_close_ms = candle.t_close_ms

        # Проходим по копии списка, чтобы можно было модифицировать оригинал
        for pos in list(self.open_positions):
            if pos.symbol != symbol:
                continue
            if pos.closed:
                continue

            self._process_position_on_candle(pos, high, low, t_close_ms)

        # Удаляем закрытые позиции из списка открытых
        self.open_positions = [p for p in self.open_positions if not p.closed]

    # ---------- Внутренняя логика ----------

    def _get_entry_price(self, symbol: str, direction: str) -> Optional[float]:
        """
        Имитация входа по рынку: берём bid/ask из тикера.
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
        except Exception as e:
            print(f"❌ Ошибка получения тикера для {symbol}: {e}")
            return None

        bid = ticker.get("bid")
        ask = ticker.get("ask")
        last = ticker.get("last")

        if direction == "bull":
            # Покупка по рынку — ближе к ask
            return ask or last or bid
        else:
            # Продажа по рынку — ближе к bid
            return bid or last or ask

    def _calc_stop_loss(self, direction: str, h: float, l: float) -> float:
        """
        SL от свечи сигнала:
        - long: чуть ниже low
        - short: чуть выше high
        """
        if direction == "bull":
            offset = l * self.sl_offset_pct
            return l - offset
        else:
            offset = h * self.sl_offset_pct
            return h + offset

    def _calc_take_profits(self, direction: str, entry_price: float, sl: float) -> tuple[float, float]:
        """
        TP1 = 1.5R, TP2 = 3R, где R = |entry - SL|.
        """
        risk = abs(entry_price - sl)
        if direction == "bull":
            tp1 = entry_price + 1.5 * risk
            tp2 = entry_price + 3.0 * risk
        else:
            tp1 = entry_price - 1.5 * risk
            tp2 = entry_price - 3.0 * risk
        return tp1, tp2

    def _calc_qty(self, size_usdt: float, entry_price: float, direction: str) -> float:
        """
        Количество монет: 100 USDT / цена.
        Для short просто делаем qty отрицательным.
        """
        if entry_price <= 0:
            return 0.0
        qty = size_usdt / entry_price
        if direction == "bear":
            qty = -qty
        return qty

    def _process_position_on_candle(
        self,
        pos: Position,
        high: float,
        low: float,
        t_close_ms: int,
    ):
        """
        Проверка, что цена пришла первой — к SL, TP1 или TP2.
        Логика:
        - всегда сначала проверяем SL;
        - затем TP1 (если ещё не был);
        - затем TP2.
        """
        remaining_qty = pos.remaining_qty()
        if remaining_qty == 0:
            # На всякий случай
            self._close_position_if_done(pos, t_close_ms)
            return

        if pos.direction == "long":
            self._process_long_position(pos, high, low, t_close_ms)
        else:
            self._process_short_position(pos, high, low, t_close_ms)

    def _process_long_position(
        self,
        pos: Position,
        high: float,
        low: float,
        t_close_ms: int,
    ):
        # 1. Проверяем SL
        if low <= pos.sl:
            self._close_full_at_price(pos, pos.sl, t_close_ms, reason="SL")
            return

        # 2. TP1 (если ещё не был)
        if not pos.tp1_hit and high >= pos.tp1:
            self._close_half_at_price(pos, pos.tp1, t_close_ms, reason="TP1")
            # Переносим SL в безубыток
            pos.sl = pos.entry_price
            pos.tp1_hit = True

        # 3. TP2 (если есть ещё объём)
        remaining_qty = pos.remaining_qty()
        if remaining_qty != 0 and high >= pos.tp2:
            self._close_full_at_price(pos, pos.tp2, t_close_ms, reason="TP2")

    def _process_short_position(
        self,
        pos: Position,
        high: float,
        low: float,
        t_close_ms: int,
    ):
        # 1. SL
        if high >= pos.sl:
            self._close_full_at_price(pos, pos.sl, t_close_ms, reason="SL")
            return

        # 2. TP1
        if not pos.tp1_hit and low <= pos.tp1:
            self._close_half_at_price(pos, pos.tp1, t_close_ms, reason="TP1")
            # Безубыток
            pos.sl = pos.entry_price
            pos.tp1_hit = True

        # 3. TP2
        remaining_qty = pos.remaining_qty()
        if remaining_qty != 0 and low <= pos.tp2:
            self._close_full_at_price(pos, pos.tp2, t_close_ms, reason="TP2")

    def _close_half_at_price(self, pos: Position, price: float, t_close_ms: int, reason: str):
        remaining_qty = pos.remaining_qty()
        if remaining_qty == 0:
            return

        half_qty = remaining_qty / 2.0
        half_size_usdt = pos.remaining_size_usdt() / 2.0

        part = TradePart(
            size_usdt=half_size_usdt,
            qty=half_qty,
            entry_price=pos.entry_price,
            exit_price=price,
            exit_time_ms=t_close_ms,
            reason=reason,
        )
        pos.parts.append(part)

        print(
            f"PAPER PART #{pos.id}: {pos.symbol} {pos.timeframe} {pos.direction} "
            f"{reason} qty={half_qty:.6f} exit={price:.4f} pnl={part.pnl_usdt:.2f}USDT "
            f"({part.pnl_percent:.2f}%)"
        )

        self._close_position_if_done(pos, t_close_ms)

    def _close_full_at_price(self, pos: Position, price: float, t_close_ms: int, reason: str):
        remaining_qty = pos.remaining_qty()
        if remaining_qty == 0:
            return

        remaining_size_usdt = pos.remaining_size_usdt()

        part = TradePart(
            size_usdt=remaining_size_usdt,
            qty=remaining_qty,
            entry_price=pos.entry_price,
            exit_price=price,
            exit_time_ms=t_close_ms,
            reason=reason,
        )
        pos.parts.append(part)

        print(
            f"PAPER CLOSE #{pos.id}: {pos.symbol} {pos.timeframe} {pos.direction} "
            f"{reason} qty={remaining_qty:.6f} exit={price:.4f} pnl={part.pnl_usdt:.2f}USDT "
            f"({part.pnl_percent:.2f}%)"
        )

        self._close_position_if_done(pos, t_close_ms)

    def _close_position_if_done(self, pos: Position, t_close_ms: int):
        # Если ещё есть объём — сделка не завершена
        if pos.remaining_qty() != 0:
            return

        # Фиксируем закрытие
        pos.closed = True
        pos.closed_at_ms = t_close_ms

        # Итоговый PnL
        total_pnl_usdt = sum(p.pnl_usdt for p in pos.parts)
        total_pnl_percent = (
            total_pnl_usdt / pos.size_usdt * 100.0
            if pos.size_usdt else 0.0
        )

        # --- Флаги достижения уровней ---
        tp1_hit = any(p.reason == "TP1" for p in pos.parts)
        tp2_hit = any(p.reason == "TP2" for p in pos.parts)
        sl_hit  = any(p.reason == "SL"  for p in pos.parts)

        # --- Причина закрытия ---
        if tp2_hit:
            close_reason = "TP1+TP2"
        elif tp1_hit and sl_hit:
            close_reason = "TP1+SL"
        elif sl_hit:
            close_reason = "SL-only"
        else:
            close_reason = None

        # --- Формируем CompletedTrade ---
        trade = CompletedTrade(
            id=pos.id,
            symbol=pos.symbol,
            timeframe=pos.timeframe,
            direction=pos.direction,
            setup=pos.setup,
            opened_at_ms=pos.opened_at_ms,
            closed_at_ms=pos.closed_at_ms,

            entry_price=pos.entry_price,
            size_usdt=pos.size_usdt,

            tp1_price=pos.tp1,
            tp2_price=pos.tp2,
            sl_price=pos.sl,

            tp1_hit=tp1_hit,
            tp2_hit=tp2_hit,
            sl_hit=sl_hit,

            close_reason=close_reason,

            pnl_usdt=total_pnl_usdt,
            pnl_percent=total_pnl_percent,

            parts=list(pos.parts),
        )

        # Добавляем в историю
        self.completed_trades.append(trade)

        print(
            f"PAPER DONE #{trade.id}: {trade.symbol} {trade.timeframe} {trade.direction} "
            f"pnl={trade.pnl_usdt:.2f}USDT ({trade.pnl_percent:.2f}%)"
        )

        # Сохраняем JSON
        self.save_trades_to_json()


    # ---------- Вспомогательные методы для отчётности ----------

    def get_equity(self) -> float:
        """
        Текущий баланс = initial + суммарный PnL по закрытым сделкам.
        (Открытые позиции не учитываем, можно добавить позже).
        """
        total_pnl = sum(t.pnl_usdt for t in self.completed_trades)
        return self.initial_balance_usdt + total_pnl

    def export_to_csv(self, path: str) -> None:
        """
        Экспорт всех завершённых сделок в CSV.
        """
        export_trades_to_csv(self.completed_trades, path)

    def print_stats(self) -> None:
        """
        Печать статистики по сделкам (по каждому сетапу).
        """
        print_stats_for_trades(self.completed_trades)

    def plot_equity_curve(self, setup: str) -> None:
        """
        Построение equity-curve по конкретному сетапу.
        """
        plot_equity_curve_for_trades(self.completed_trades, setup, self.initial_balance_usdt)

    def save_trades_to_json(self, path: str = "web/backend/app/data/trades.json") -> None:
        """
        Сохраняет все завершённые сделки в JSON-файл,
        чтобы backend (FastAPI) мог их читать.
        """
        import json
        from pathlib import Path

        # Преобразуем CompletedTrade → dict
        data = [t.dict() for t in self.completed_trades]

        # Создаём директорию, если её нет
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        # Записываем JSON
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"💾 Trades saved to JSON: {path}")


def make_paper_trading_handler(engine: PaperTradingEngine):
    """
    Адаптер под SignalRouter: handler(signal: Signal).
    """
    def handler(signal: Signal):
        engine.on_signal(signal)
    return handler
