# falling_star_daemon.py

import os
import time
from dataclasses import dataclass
from collections import deque
from typing import Dict, Deque, Tuple, List

import ccxt
from dotenv import load_dotenv

from utils.timeframes import tf_seconds

from setup_manager import SetupManager
from setups import FallingStarSetup, HammerSetup, MaxVolumeZoneSetup, RSIZoneSetup
from models import Candle

from signal_router import SignalRouter
from handlers.telegram_handler import make_telegram_handler
from handlers.log_handler import log_handler
from handlers.paper_trading import PaperTradingEngine, make_paper_trading_handler


@dataclass
class Config:
    exchange_id: str
    symbols: list[str]
    timeframes: list[str]
    tz: str
    tg_token: str
    tg_chat_id: str
    poll_sec: float = 5.0


def load_config() -> Config:
    load_dotenv()
    exchange_id = (os.getenv("EXCHANGE_ID") or "binance").strip()
    symbols = [s.strip() for s in (os.getenv("SYMBOLS") or "BTC/USDT").split(",") if s.strip()]
    timeframes = [t.strip() for t in (os.getenv("TIMEFRAMES") or "5m").split(",") if t.strip()]
    tz = (os.getenv("TZ") or "Europe/Helsinki").strip()
    tg_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    tg_chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    return Config(exchange_id, symbols, timeframes, tz, tg_token, tg_chat_id)


def make_exchange(exchange_id: str) -> ccxt.Exchange:
    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class(
        {
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        }
    )
    exchange.load_markets()
    return exchange

Store = Dict[Tuple[str, str], Deque[Tuple[int, float, float, float, float]]]

def ts_close_from_open(t_open_ms: int, timeframe_sec: int) -> int:
    return t_open_ms + timeframe_sec * 1000

def main():
    cfg = load_config()

    exchange = make_exchange(cfg.exchange_id)
    # создаём движок бумажной торговли
    paper_engine = PaperTradingEngine(exchange)

    router = SignalRouter(
        handlers=[
            make_telegram_handler(cfg.tg_token, cfg.tg_chat_id, cfg.tz), 
            log_handler, 
            make_paper_trading_handler(paper_engine),
        ]
    )
    
    setup_manager = SetupManager(
        setups=[
            FallingStarSetup(),
            HammerSetup(),
            MaxVolumeZoneSetup(exchange, cfg),
            RSIZoneSetup(exchange, cfg),
        ]
    )

    last_seen_close: Dict[Tuple[str, str], int] = {}
    store: Store = {}

    for symbol in cfg.symbols:
        for timeframe in cfg.timeframes:
            key = (symbol, timeframe)
            try:
                limit = 10
                raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
                if not raw or len(raw) < 2:
                    print(f"⚠️ Недостаточно данных: {symbol} {timeframe}")
                    continue

                timeframe_sec = tf_seconds(exchange, timeframe)

                closed_rows = raw[:-1]
                deque5: Deque[Candle] = deque(maxlen=5)

                for row in closed_rows[-5:]:
                    t_open_ms, o, h, l, c, *_ = row
                    t_close_ms = ts_close_from_open(int(t_open_ms), timeframe_sec)
                    deque5.append(
                        (
                            t_close_ms,
                            float(o),
                            float(h),
                            float(l),
                            float(c),
                        )
                    )

                store[key] = deque5

                if deque5:
                    last_seen_close[key] = deque5[-1][0]

            except Exception as e:
                print(f"❌ Предзаполнение {symbol} {timeframe}: {e}")

            time.sleep(0.15)

    print("🟢 Старт мониторинга…")

    while True:
        for symbol in cfg.symbols:
            for timeframe in cfg.timeframes:
                key = (symbol, timeframe)
                try:
                    limit = 10
                    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
                    if not raw or len(raw) < 2:
                        continue

                    timeframe_sec = tf_seconds(exchange, timeframe)

                    closed_records: List[Tuple[int, float, float, float, float]] = []
                    for row in raw[:-1]: 
                        t_open_ms, o, h, l, c, *_ = row 
                        t_close_ms = ts_close_from_open(int(t_open_ms), timeframe_sec) 
                        closed_records.append( ( 
                            t_close_ms, 
                            float(o), 
                            float(h), 
                            float(l), 
                            float(c), 
                            ) 
                        )
                    
                    closed_records.sort(key=lambda x: x[0])

                    last_close_ts = last_seen_close.get(key, 0)

                    for (t_close_ms, o, h, l, c) in closed_records:
                        if t_close_ms <= last_close_ts:
                            continue

                        candle = Candle(
                            symbol=symbol,
                            timeframe=timeframe,
                            t_close_ms=t_close_ms,
                            o=o,
                            h=h,
                            l=l,
                            c=c,
                        )

                        # 1. Сначала даём свечу PaperTradingEngine (для отработки SL/TP по уже открытым позициям) 
                        paper_engine.on_candle(candle)
                        
                        # 2. Генерируем сигналы
                        signals = setup_manager.process_candle(candle)

                        # 3. Обогащаем сигналы данными свечи (для открытия новых позиций)
                        for sig in signals: 
                            sig.extra.setdefault("candle", { 
                                "o": candle.o, 
                                "h": candle.h, 
                                "l": candle.l, 
                                "c": candle.c, 
                            }) 
                            router.route(sig)

                        deque_for_key = store.get(key)
                        if deque_for_key is None:
                            deque_for_key = deque(maxlen=5)
                            store[key] = deque_for_key
                        deque_for_key.append((t_close_ms, o, h, l, c))

                        last_seen_close[key] = t_close_ms
                        last_close_ts = t_close_ms

                    if closed_records:
                        last5 = closed_records[-5:]
                        deque_for_key = deque(last5, maxlen=5)
                        store[key] = deque_for_key

                except ccxt.RateLimitExceeded as e:
                    print(f"⏳ Rate limit {symbol} {timeframe}: {e}; пауза 2с")
                    time.sleep(2)
                except Exception as e:
                    print(f"❌ Ошибка {symbol} {timeframe}: {e}")

                time.sleep(0.15)

        time.sleep(cfg.poll_sec)


if __name__ == "__main__":
    main()
