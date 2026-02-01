Команды
запуск  python falling_star_daemon.py



ВЕРСИИ ПРОГИ
Версия 1.1. (проверяет 1 раз, без постоянной проверки) 

в проге 2 файла 
.env  
falling_star_scanner.py

файл  - .env

# Биржа (оставь binance — это спот)
EXCHANGE_ID=binance

# Список тикеров через запятую
SYMBOLS=BTC/USDT,ETH/USDT,SUI/USDT,XRP/USDT,TON/USDT

# Список таймфреймов через запятую (как в ccxt)
TIMEFRAMES=5m,15m,1h,4h

# Часовой пояс для показа времени (PEP 615)
TZ=Europe/Helsinki

# Данные телеграм-бота
TELEGRAM_BOT_TOKEN=7254176176:AAGm8jbpzJ_lxq3ak2cjKtEU3pT9LAVkEhA
TELEGRAM_CHAT_ID=6956974295   # свой chat_id


__________________________________________________________________________________________
файл  - falling_star_scanner.py

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import requests
import ccxt
from dotenv import load_dotenv


# ============ Настройки / конфиг ============

@dataclass
class Config:
    exchange_id: str
    symbols: list[str]
    timeframes: list[str]
    tz: str
    tg_token: str
    tg_chat_id: str


def load_config() -> Config:
    load_dotenv()
    exchange_id = (os.getenv("EXCHANGE_ID") or "binance").strip()
    symbols_raw = os.getenv("SYMBOLS") or "BTC/USDT"
    timeframes_raw = os.getenv("TIMEFRAMES") or "5m"
    tz = (os.getenv("TZ") or "Europe/Helsinki").strip()
    tg_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    tg_chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

    symbols = [s.strip() for s in symbols_raw.split(",") if s.strip()]
    timeframes = [t.strip() for t in timeframes_raw.split(",") if t.strip()]

    return Config(
        exchange_id=exchange_id,
        symbols=symbols,
        timeframes=timeframes,
        tz=tz,
        tg_token=tg_token,
        tg_chat_id=tg_chat_id,
    )


# ============ Телеграм ============

def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    if not token or not chat_id:
        print("⚠️  TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID пусты — сообщение не отправлено")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
        "parse_mode": "HTML",
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"❌ Ошибка отправки в Telegram: {e}")


# ============ Правило Falling Star ============

def _is_falling_star_by_ohlc(o: float, h: float, l: float, c: float) -> bool:
    """
    Упрощённые правила Falling Star:
      - тело мало: |o - c| <= 0.3 * (h - l)
      - верхняя тень большая: (h - max(o, c)) >= 0.6 * (h - l)
      - нижняя тень маленькая: (min(o, c) - l) <= 0.15 * (h - l)
    """
    rng = max(h - l, 1e-12)
    body = abs(o - c)
    upper = h - max(o, c)
    lower = min(o, c) - l
    return (body <= 0.3 * rng) and (upper >= 0.6 * rng) and (lower <= 0.15 * rng)


# ============ Работа со свечами через ccxt ============

def make_exchange(exchange_id: str) -> ccxt.Exchange:
    cls = getattr(ccxt, exchange_id)
    ex = cls({
        "enableRateLimit": True,
        "options": {
            # важно для корректной длины свечи
            "defaultType": "spot",
        }
    })
    ex.load_markets()
    return ex


def get_last_closed_candle(ex: ccxt.Exchange, symbol: str, timeframe: str):
    """
    Возвращает кортеж:
      (t_open_ms, t_close_ms, o, h, l, c)
    Берём «предпоследнюю» свечу из fetch_ohlcv: последняя — текущая формирующаяся.
    """
    # Берём пару-тройку последних, чтобы наверняка иметь закрытую
    ohlcv = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=3)
    if not ohlcv or len(ohlcv) < 2:
        raise RuntimeError("Недостаточно данных OHLCV")

    # ccxt.timestamp у OHLCV — время ОТКРЫТИЯ свечи
    t_open, o, h, l, c, *_ = ohlcv[-2]  # предпоследняя — закрытая
    sec = ex.parse_timeframe(timeframe)
    t_close = t_open + sec * 1000
    return t_open, t_close, float(o), float(h), float(l), float(c)


def ts_to_local_str(ts_ms: int, tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).astimezone(tz)
    # Округлим до минут:
    dt = dt.replace(second=0, microsecond=0)
    return dt.strftime("%Y-%m-%d %H:%M")


# ============ Основной сценарий ============

def main():
    cfg = load_config()
    ex = make_exchange(cfg.exchange_id)

    for symbol in cfg.symbols:
        for tf in cfg.timeframes:
            try:
                t_open, t_close, o, h, l, c = get_last_closed_candle(ex, symbol, tf)
                if _is_falling_star_by_ohlc(o, h, l, c):
                    when_local = ts_to_local_str(t_close, cfg.tz)
                    msg = f"{symbol} — Falling Star — {when_local} ({tf})"
                    print("ALERT:", msg)
                    send_telegram_message(cfg.tg_token, cfg.tg_chat_id, msg)
                else:
                    print(f"{symbol} {tf}: совпадения нет (закрытая свеча {ts_to_local_str(t_close, cfg.tz)})")
            except Exception as e:
                print(f"❌ {symbol} {tf}: ошибка — {e}")
            # бережно относимся к rate limit
            time.sleep(0.3)


if __name__ == "__main__":
    main()










Версия 1.2. (проверяет постоянно) 

в проге 2 файла 
.env  
falling_star_deamon.py
__________________________________________________________________________________________
файл  - .env (не менялся с версии 1.1.)

# Биржа (оставь binance — это спот)
EXCHANGE_ID=binance

# Список тикеров через запятую
SYMBOLS=BTC/USDT,ETH/USDT,SUI/USDT,XRP/USDT,TON/USDT

# Список таймфреймов через запятую (как в ccxt)
TIMEFRAMES=5m,15m,1h,4h

# Часовой пояс для показа времени (PEP 615)
TZ=Europe/Helsinki

# Данные телеграм-бота
TELEGRAM_BOT_TOKEN=7254176176:AAGm8jbpzJ_lxq3ak2cjKtEU3pT9LAVkEhA
TELEGRAM_CHAT_ID=6956974295   # свой chat_id

__________________________________________________________________________________________
файл - falling_star_scanner.py удален, вместо него теперь falling_star_deamon.py

__________________________________________________________________________________________
файл falling_star_deamon.py

import os
import time
from dataclasses import dataclass
from collections import deque
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Deque, Tuple, List

import requests
import ccxt
from dotenv import load_dotenv


# ========== Конфиг ==========
@dataclass
class Config:
    exchange_id: str
    symbols: list[str]
    timeframes: list[str]
    tz: str
    tg_token: str
    tg_chat_id: str
    poll_sec: float = 5.0   # частота опроса API (сек)

def load_config() -> Config:
    load_dotenv()
    exchange_id = (os.getenv("EXCHANGE_ID") or "binance").strip()
    symbols = [s.strip() for s in (os.getenv("SYMBOLS") or "BTC/USDT").split(",") if s.strip()]
    timeframes = [t.strip() for t in (os.getenv("TIMEFRAMES") or "5m").split(",") if t.strip()]
    tz = (os.getenv("TZ") or "Europe/Helsinki").strip()
    tg_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    tg_chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    return Config(exchange_id, symbols, timeframes, tz, tg_token, tg_chat_id)


# ========== Телеграм ==========
def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    if not token or not chat_id:
        print("⚠️ TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID пусты — пропускаю отправку")
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=10,
        )
        r.raise_for_status()
    except Exception as e:
        print(f"❌ Ошибка отправки в Telegram: {e}")


# ========== Паттерн Falling Star ==========
def _is_falling_star_by_ohlc(o: float, h: float, l: float, c: float) -> bool:
    """
    Упрощённые правила Falling Star:
      - тело мало: |o - c| <= 0.3 * (h - l)
      - верхняя тень большая: (h - max(o, c)) >= 0.6 * (h - l)
      - нижняя тень маленькая: (min(o, c) - l) <= 0.15 * (h - l)
    """
    rng = max(h - l, 1e-12)
    body = abs(o - c)
    upper = h - max(o, c)
    lower = min(o, c) - l
    return (body <= 0.3 * rng) and (upper >= 0.6 * rng) and (lower <= 0.15 * rng)


# ========== Вспомогательные ==========
def make_exchange(exchange_id: str) -> ccxt.Exchange:
    ex_cls = getattr(ccxt, exchange_id)
    ex = ex_cls({
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
    })
    ex.load_markets()
    return ex

def tf_seconds(ex: ccxt.Exchange, timeframe: str) -> int:
    return ex.parse_timeframe(timeframe)

def ts_close_from_open(t_open_ms: int, tf_sec: int) -> int:
    return t_open_ms + tf_sec * 1000

def ts_to_local_str(ts_ms: int, tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).astimezone(tz)
    return dt.strftime("%Y-%m-%d %H:%M")


# Типы для хранилища 5 свечей
Candle = Tuple[int, float, float, float, float]  # (t_close_ms, o, h, l, c)
Store = Dict[Tuple[str, str], Deque[Candle]]    # key=(symbol, tf) -> deque(maxlen=5)


# ========== Основной цикл ==========
def main():
    cfg = load_config()
    ex = make_exchange(cfg.exchange_id)

    # Последнее обработанное закрытие (чтобы не слать повторно)
    last_seen_close: Dict[Tuple[str, str], int] = {}
    # Хранилище последних 5 закрытых свечей на ключ (symbol, timeframe)
    store: Store = {}

    # Предзаполним хранилище «тихим» состоянием (без отправки истории)
    for symbol in cfg.symbols:
        for tf in cfg.timeframes:
            key = (symbol, tf)
            try:
                limit = 10  # взять небольшой буфер
                raw = ex.fetch_ohlcv(symbol, timeframe=tf, limit=limit)
                if not raw or len(raw) < 2:
                    print(f"⚠️ Недостаточно данных: {symbol} {tf}")
                    continue
                tf_sec = tf_seconds(ex, tf)

                # исключаем последнюю формирующуюся: берём закрытые raw[:-1]
                closed = raw[:-1]
                # соберём и ограничим последними 5
                deque5: Deque[Candle] = deque(maxlen=5)
                for r in closed[-5:]:
                    t_open, o, h, l, c, *_ = r
                    t_close = ts_close_from_open(int(t_open), tf_sec)
                    deque5.append((t_close, float(o), float(h), float(l), float(c)))
                store[key] = deque5
                # инициализируем last_seen_close последним закрытием
                if deque5:
                    last_seen_close[key] = deque5[-1][0]
            except Exception as e:
                print(f"❌ Предзаполнение {symbol} {tf}: {e}")

            time.sleep(0.15)  # щадим API

    print("🟢 Старт мониторинга…")

    # Бесконечный мониторинг
    while True:
        for symbol in cfg.symbols:
            for tf in cfg.timeframes:
                key = (symbol, tf)
                try:
                    limit = 10
                    raw = ex.fetch_ohlcv(symbol, timeframe=tf, limit=limit)
                    if not raw or len(raw) < 2:
                        continue
                    tf_sec = tf_seconds(ex, tf)

                    # список закрытых свечей, по возрастанию времени закрытия
                    closed_records: List[Candle] = []
                    for r in raw[:-1]:  # исключаем текущую формирующуюся
                        t_open, o, h, l, c, *_ = r
                        t_close = ts_close_from_open(int(t_open), tf_sec)
                        closed_records.append((t_close, float(o), float(h), float(l), float(c)))
                    closed_records.sort(key=lambda x: x[0])

                    # обработаем все НОВЫЕ закрытия (их может быть несколько)
                    last_close = last_seen_close.get(key, 0)
                    for (t_close, o, h, l, c) in closed_records:
                        if t_close <= last_close:
                            continue  # уже видели
                        # 1) проверка паттерна
                        if _is_falling_star_by_ohlc(o, h, l, c):
                            when_local = ts_to_local_str(t_close, cfg.tz)
                            msg = f"{symbol} — Falling Star — {when_local} ({tf})"
                            print("ALERT:", msg)
                            send_telegram_message(cfg.tg_token, cfg.tg_chat_id, msg)
                        else:
                            print(f"{symbol} {tf}: нет сигнала ({ts_to_local_str(t_close, cfg.tz)})")

                        # 2) положим свечу в хранилище (не более 5)
                        dq = store.get(key)
                        if dq is None:
                            dq = deque(maxlen=5)
                            store[key] = dq
                        dq.append((t_close, o, h, l, c))

                        # 3) обновим «последнее обработанное закрытие»
                        last_seen_close[key] = t_close

                    # синхронизируем хранилище с фактическими последними 5 закрытиями на всякий случай
                    # (если кто-то перезапустил процесс и проскочили свечи)
                    if closed_records:
                        last5 = closed_records[-5:]
                        dq = deque(last5, maxlen=5)
                        store[key] = dq
                        # last_seen_close НЕ трогаем здесь — он обновляется только при обработке новых

                except ccxt.RateLimitExceeded as e:
                    print(f"⏳ Rate limit {symbol} {tf}: {e}; пауза 2с")
                    time.sleep(2)
                except Exception as e:
                    print(f"❌ Ошибка {symbol} {tf}: {e}")

                time.sleep(0.15)  # межзапросная пауза

        time.sleep(cfg.poll_sec)


if __name__ == "__main__":
    main()


_____________________________________________________________________
ВЕРСИИ ПРОГИ
Версия 1.3. (добавлены обьем на кончике фитиля, RSI, молоток (еще не проверен в работе))
перед выносом отправки в отдельный файл и сетапов в отдельный файл создал этот слепок.

.env
# Биржа (оставь binance — это спот)
EXCHANGE_ID=binance

# Список тикеров через запятую
SYMBOLS=BTC/USDT,ETH/USDT,SUI/USDT,XRP/USDT,TON/USDT

# Список таймфреймов через запятую (как в ccxt)
TIMEFRAMES=5m,15m,1h,4h

# Часовой пояс для показа времени (PEP 615)
TZ=Europe/Moscow

# Данные телеграм-бота
TELEGRAM_BOT_TOKEN=7254176176:AAGm8jbpzJ_lxq3ak2cjKtEU3pT9LAVkEhA
TELEGRAM_CHAT_ID=6956974295   # свой chat_id


=====================================================================
falling_star_daemon.py

import os
import time
from dataclasses import dataclass
from collections import deque
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Deque, Tuple, List

import requests
import ccxt
from dotenv import load_dotenv

from hammer_setup import analyze_hammer

# ========== Конфиг ==========

@dataclass
class Config:
    exchange_id: str
    symbols: list[str]
    timeframes: list[str]
    tz: str
    tg_token: str
    tg_chat_id: str
    poll_sec: float = 5.0   # частота опроса API (сек)


def load_config() -> Config:
    load_dotenv()
    exchange_id = (os.getenv("EXCHANGE_ID") or "binance").strip()
    symbols = [s.strip() for s in (os.getenv("SYMBOLS") or "BTC/USDT").split(",") if s.strip()]
    timeframes = [t.strip() for t in (os.getenv("TIMEFRAMES") or "5m").split(",") if t.strip()]
    tz = (os.getenv("TZ") or "Europe/Helsinki").strip()
    tg_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    tg_chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    return Config(exchange_id, symbols, timeframes, tz, tg_token, tg_chat_id)


# ========== Телеграм ==========

def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    if not token or not chat_id:
        print("⚠️ TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID пусты — пропускаю отправку")
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        r.raise_for_status()
    except Exception as e:
        print(f"❌ Ошибка отправки в Telegram: {e}")


# ========== Паттерн Falling Star ==========

def _is_falling_star_by_ohlc(o: float, h: float, l: float, c: float) -> bool:
    """
    Упрощённые правила Falling Star:
      - тело мало: |o - c| <= 0.3 * (h - l)
      - верхняя тень большая: (h - max(o, c)) >= 0.6 * (h - l)
      - нижняя тень маленькая: (min(o, c) - l) <= 0.15 * (h - l)
    """
    range_high_low = max(h - l, 1e-12)
    body_size = abs(o - c)
    upper_shadow = h - max(o, c)
    lower_shadow = min(o, c) - l
    return (
        body_size <= 0.3 * range_high_low
        and upper_shadow >= 0.6 * range_high_low
        and lower_shadow <= 0.15 * range_high_low
    )


# ========== Вспомогательные функции времени / биржи ==========

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


def tf_seconds(exchange: ccxt.Exchange, timeframe: str) -> int:
    return exchange.parse_timeframe(timeframe)


def ts_close_from_open(t_open_ms: int, timeframe_sec: int) -> int:
    return t_open_ms + timeframe_sec * 1000


def ts_to_local_str(ts_ms: int, tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).astimezone(tz)
    return dt.strftime("%Y-%m-%d %H:%M")


def now_local_str(tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    dt = datetime.now(timezone.utc).astimezone(tz)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# Типы для хранилища 5 свечей Falling Star
Candle = Tuple[int, float, float, float, float]  # (t_close_ms, o, h, l, c)
Store = Dict[Tuple[str, str], Deque[Candle]]     # key=(symbol, timeframe) -> deque(maxlen=5)

def compute_rsi(closes: List[float], period: int = 14) -> float | None:
    """
    Расчёт RSI по формуле Wilder (RSI-14).
    """
    if len(closes) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(1, period + 1):
        diff = closes[-i] - closes[-i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(-diff)

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def analyze_rsi_zone(
    exchange: ccxt.Exchange,
    symbol: str,
    timeframe: str,
    candle_close_ts_ms: int,
    cfg: Config,
) -> None:
    """
    Сетап RSI Zone Entry:
    - RSI <= 20 → oversold
    - RSI >= 80 → overbought
    - анализ только закрытой свечи
    """

    # Загружаем историю свечей
    try:
        raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=100)
    except Exception as e:
        print(f"❌ {symbol} {timeframe}: ошибка получения OHLCV для RSI — {e}")
        return

    if not raw or len(raw) < 15:
        print(f"{symbol} {timeframe}: RSI — недостаточно данных")
        return

    timeframe_sec = tf_seconds(exchange, timeframe)

    # Оставляем только закрытые свечи
    closed_records = []
    for row in raw:
        t_open_ms, o, h, l, c, *_ = row
        t_close_ms = ts_close_from_open(int(t_open_ms), timeframe_sec)
        if t_close_ms <= candle_close_ts_ms:
            closed_records.append((t_close_ms, o, h, l, c))

    if len(closed_records) < 15:
        print(f"{symbol} {timeframe}: RSI — мало закрытых свечей")
        return

    closed_records.sort(key=lambda x: x[0])

    # Проверяем совпадение времени
    if closed_records[-1][0] != candle_close_ts_ms:
        return

    closes = [c[4] for c in closed_records]
    rsi = compute_rsi(closes, period=14)
    if rsi is None:
        return

    # Время свечи
    candle_open_ts_ms = candle_close_ts_ms - timeframe_sec * 1000
    tz = ZoneInfo(cfg.tz)
    open_str = datetime.fromtimestamp(candle_open_ts_ms / 1000, tz).strftime("%Y-%m-%d %H:%M")
    close_str = datetime.fromtimestamp(candle_close_ts_ms / 1000, tz).strftime("%Y-%m-%d %H:%M")

    # Определяем сигнал
    if rsi <= 20:
        direction = "oversold"
    elif rsi >= 80:
        direction = "overbought"
    else:
        print(f"{symbol} {timeframe}: RSI — нет сигнала ({open_str}–{close_str}) значение: {rsi:.2f}")
        return

    # Вывод в консоль
    print(f"{symbol} {timeframe}: RSI — {direction} ({open_str}–{close_str}) значение: {rsi:.2f}")

    # Telegram
    message = (
        f"{symbol} — RSI — {direction} — {open_str}–{close_str} ({timeframe})\n"
        f"RSI value: {rsi:.2f}\n"
        f"Signal time: {now_local_str(cfg.tz)}"
    )
    send_telegram_message(cfg.tg_token, cfg.tg_chat_id, message)

# ========== Сетап Max_Volume_Zone (объём по ценовым зонам) ==========

def analyze_max_volume_zone(
    exchange: ccxt.Exchange,
    symbol: str,
    timeframe: str,
    candle_high: float,
    candle_low: float,
    candle_close_ts_ms: int,
    cfg: Config,
) -> None:
    """
    Новая версия Max_Volume_Zone:
    - анализ только закрытой свечи TF
    - расчёт начала и конца свечи
    - вывод в стиле Falling Star
    """

    # === 1. Определяем длину TF ===
    timeframe_sec = tf_seconds(exchange, timeframe)
    if timeframe_sec <= 0:
        return

    candle_open_ts_ms = candle_close_ts_ms - timeframe_sec * 1000

    # === 2. Переводим время в локальную зону ===
    tz = ZoneInfo(cfg.tz)
    dt_open = datetime.fromtimestamp(candle_open_ts_ms / 1000, tz)
    dt_close = datetime.fromtimestamp(candle_close_ts_ms / 1000, tz)

    open_str = dt_open.strftime("%Y-%m-%d %H:%M")
    close_str = dt_close.strftime("%Y-%m-%d %H:%M")

    # === 3. Проверяем диапазон свечи ===
    price_range = candle_high - candle_low
    if price_range <= 0:
        print(f"{symbol} {timeframe}: Max_Volume_Zone — нет сигнала ({open_str}–{close_str})")
        return

    # === 4. Делим диапазон на 5 зон ===
    price_step = price_range / 5.0

    # === 5. Загружаем минутные свечи внутри TF ===
    timeframe_minutes = timeframe_sec // 60
    minutes_limit = timeframe_minutes + 5

    try:
        raw_minutes = exchange.fetch_ohlcv(
            symbol,
            timeframe="1m",
            since=candle_open_ts_ms,
            limit=minutes_limit,
        )
    except Exception as e:
        print(f"❌ {symbol} {timeframe}: ошибка получения 1m — {e}")
        return

    if not raw_minutes:
        print(f"{symbol} {timeframe}: Max_Volume_Zone — нет минутных данных ({open_str}–{close_str})")
        return

    # === 6. Фильтруем минутные свечи внутри интервала ===
    zone_volumes = [0.0] * 5

    for row in raw_minutes:
        if len(row) < 6:
            continue

        minute_open_ts_ms, o, h, l, c, vol = row[:6]

        if not (candle_open_ts_ms <= minute_open_ts_ms < candle_close_ts_ms):
            continue

        minute_high = float(h)
        minute_low = float(l)
        mid_price = (minute_high + minute_low) / 2.0

        distance_from_low = mid_price - candle_low
        if distance_from_low < 0 or distance_from_low > price_range:
            continue

        zone_index_from_bottom = int(distance_from_low // price_step)
        if zone_index_from_bottom >= 5:
            zone_index_from_bottom = 4

        zone_index_from_top = 4 - zone_index_from_bottom

        zone_volumes[zone_index_from_top] += float(vol)

    # === 7. Определяем зону максимального объёма ===
    max_volume = max(zone_volumes)
    if max_volume <= 0:
        print(f"{symbol} {timeframe}: Max_Volume_Zone — нет сигнала ({open_str}–{close_str})")
        return

    max_zone_index = zone_volumes.index(max_volume)  # 0..4
    max_zone_number = max_zone_index + 1             # 1..5

    # === 8. Сигнал только если зона 1 или 5 ===
    if max_zone_number == 1:
        direction = "bear"
    elif max_zone_number == 5:
        direction = "bull"
    else:
        print(f"{symbol} {timeframe}: Max_Volume_Zone — нет сигнала ({open_str}–{close_str})")
        return

    # === 9. Вывод в консоль в стиле Falling Star ===
    print(
        f"{symbol} {timeframe}: Max_Volume_Zone — {direction} "
        f"({open_str}–{close_str})"
    )

    # === 10. Telegram — включаем обратно ===
    message = (
        f"{symbol} — Max_Volume_Zone — {direction} — "
        f"{open_str}–{close_str} ({timeframe})\n"
        f"Signal time: {now_local_str(cfg.tz)}"
    )
    send_telegram_message(cfg.tg_token, cfg.tg_chat_id, message)
    
# ========== Основной цикл ==========

def main():
    cfg = load_config()
    exchange = make_exchange(cfg.exchange_id)

    # Последнее обработанное закрытие (чтобы не слать повторно)
    last_seen_close: Dict[Tuple[str, str], int] = {}
    # Хранилище последних 5 закрытых свечей для Falling Star
    store: Store = {}

    # Предзаполним хранилище «тихим» состоянием (без отправки истории)
    for symbol in cfg.symbols:
        for timeframe in cfg.timeframes:
            key = (symbol, timeframe)
            try:
                limit = 10  # небольшой буфер
                raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
                if not raw or len(raw) < 2:
                    print(f"⚠️ Недостаточно данных: {symbol} {timeframe}")
                    continue

                timeframe_sec = tf_seconds(exchange, timeframe)

                # исключаем последнюю формирующуюся: берём закрытые raw[:-1]
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

            time.sleep(0.15)  # щадим API

    print("🟢 Старт мониторинга…")

    # Бесконечный мониторинг
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

                    # список закрытых свечей, по возрастанию времени закрытия
                    closed_records: List[Candle] = []
                    for row in raw[:-1]:  # исключаем текущую формирующуюся
                        t_open_ms, o, h, l, c, *_ = row
                        t_close_ms = ts_close_from_open(int(t_open_ms), timeframe_sec)
                        closed_records.append(
                            (
                                t_close_ms,
                                float(o),
                                float(h),
                                float(l),
                                float(c),
                            )
                        )
                    closed_records.sort(key=lambda x: x[0])

                    last_close_ts = last_seen_close.get(key, 0)

                    # обработаем все НОВЫЕ закрытия (их может быть несколько)
                    for (t_close_ms, o, h, l, c) in closed_records:
                        if t_close_ms <= last_close_ts:
                            continue  # уже видели

                        # ===== Сетап 1: Falling Star =====
                        if _is_falling_star_by_ohlc(o, h, l, c):
                            candle_time_local = ts_to_local_str(t_close_ms, cfg.tz)
                            message = f"{symbol} — Falling Star — {candle_time_local} ({timeframe})"
                            print("ALERT:", message)
                            send_telegram_message(cfg.tg_token, cfg.tg_chat_id, message)
                        else:
                            print(
                                f"{symbol} {timeframe}: Falling Star — нет сигнала "
                                f"({ts_to_local_str(t_close_ms, cfg.tz)})"
                            )

                        # ===== Сетап 1.5: Hammer =====
                        try:
                            analyze_hammer(
                                symbol=symbol,
                                timeframe=timeframe,
                                t_close_ms=t_close_ms,
                                o=o, h=h, l=l, c=c,
                                cfg=cfg,
                            )
                        except Exception as e:
                            print(f"❌ {symbol} {timeframe}: ошибка в Hammer — {e}")

                        # ===== Сетап 2: Max_Volume_Zone =====
                        try:
                            analyze_max_volume_zone(
                                exchange=exchange,
                                symbol=symbol,
                                timeframe=timeframe,
                                candle_high=h,
                                candle_low=l,
                                candle_close_ts_ms=t_close_ms,
                                cfg=cfg,
                            )
                        except Exception as e:
                            print(
                                f"❌ {symbol} {timeframe}: ошибка в Max_Volume_Zone — {e}"
                            )
                        
                        # ===== Сетап 3: RSI Zone Entry =====
                        try:
                            analyze_rsi_zone(
                                exchange=exchange,
                                symbol=symbol,
                                timeframe=timeframe,
                                candle_close_ts_ms=t_close_ms,
                                cfg=cfg,
                            )
                        except Exception as e:
                            print(f"❌ {symbol} {timeframe}: ошибка в RSI — {e}")

                        # Положим свечу в хранилище (не более 5) — для Falling Star /
                        # возможного будущего использования истории
                        deque_for_key = store.get(key)
                        if deque_for_key is None:
                            deque_for_key = deque(maxlen=5)
                            store[key] = deque_for_key
                        deque_for_key.append((t_close_ms, o, h, l, c))

                        # Обновим «последнее обработанное закрытие»
                        last_seen_close[key] = t_close_ms
                        last_close_ts = t_close_ms

                    # Синхронизируем хранилище с фактическими последними 5 закрытиями
                    if closed_records:
                        last5 = closed_records[-5:]
                        deque_for_key = deque(last5, maxlen=5)
                        store[key] = deque_for_key
                        # last_seen_close не трогаем — он обновляется только по новым

                except ccxt.RateLimitExceeded as e:
                    print(f"⏳ Rate limit {symbol} {timeframe}: {e}; пауза 2с")
                    time.sleep(2)
                except Exception as e:
                    print(f"❌ Ошибка {symbol} {timeframe}: {e}")

                time.sleep(0.15)  # межзапросная пауза

        time.sleep(cfg.poll_sec)


if __name__ == "__main__":
    main()

==================================================
# hammer_setup.py
from datetime import datetime
from zoneinfo import ZoneInfo

def is_hammer(o: float, h: float, l: float, c: float) -> bool:
    """
    Зеркальная логика твоей Falling Star.
    """
    range_hl = max(h - l, 1e-12)
    body = abs(o - c)
    upper_shadow = h - max(o, c)
    lower_shadow = min(o, c) - l

    return (
        body <= 0.3 * range_hl and
        lower_shadow >= 0.6 * range_hl and
        upper_shadow <= 0.15 * range_hl
    )


def analyze_hammer(symbol: str, timeframe: str, t_close_ms: int, o: float, h: float, l: float, c: float, cfg) -> None:
    """
    Анализ закрытой свечи на предмет молота.
    Формат вывода — как у Falling Star.
    """

    if is_hammer(o, h, l, c):
        candle_time_local = datetime.fromtimestamp(t_close_ms / 1000, ZoneInfo(cfg.tz)).strftime("%Y-%m-%d %H:%M")
        msg = f"{symbol} — Hammer — {candle_time_local} ({timeframe})"
        print("ALERT:", msg)
        from main import send_telegram_message
        send_telegram_message(cfg.tg_token, cfg.tg_chat_id, msg)
    else:
        print(
            f"{symbol} {timeframe}: Hammer — нет сигнала "
            f"({datetime.fromtimestamp(t_close_ms / 1000, ZoneInfo(cfg.tz)).strftime('%Y-%m-%d %H:%M')})"
        )






_____________________________________________________________________
ВЕРСИИ ПРОГИ
Версия 1.4. (вынесение сетапов в отдельные файлы в папку сетап). Делаю перед внеднрение бумажных сделок.

# file .env
# Биржа (оставь binance — это спот)
EXCHANGE_ID=binance

# Список тикеров через запятую
SYMBOLS=BTC/USDT,ETH/USDT,SUI/USDT,XRP/USDT,TON/USDT

# Список таймфреймов через запятую (как в ccxt)
TIMEFRAMES=5m,15m,1h,4h

# Часовой пояс для показа времени (PEP 615)
TZ=Europe/Moscow

# Данные телеграм-бота
TELEGRAM_BOT_TOKEN=7254176176:AAGm8jbpzJ_lxq3ak2cjKtEU3pT9LAVkEhA
TELEGRAM_CHAT_ID=6956974295   # свой chat_id


# falling_star_daemon.py

import os
import time
from dataclasses import dataclass
from collections import deque
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Deque, Tuple, List

import ccxt
from dotenv import load_dotenv

from notifier import send_telegram_message
from setups.hammer import analyze_hammer
from setups.falling_star import analyze_falling_star
from setups.max_volume_zone import analyze_max_volume_zone
from setups.rsi_zone import analyze_rsi_zone


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


def tf_seconds(exchange: ccxt.Exchange, timeframe: str) -> int:
    return exchange.parse_timeframe(timeframe)


def ts_close_from_open(t_open_ms: int, timeframe_sec: int) -> int:
    return t_open_ms + timeframe_sec * 1000


def ts_to_local_str(ts_ms: int, tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).astimezone(tz)
    return dt.strftime("%Y-%m-%d %H:%M")


def now_local_str(tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    dt = datetime.now(timezone.utc).astimezone(tz)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


Candle = Tuple[int, float, float, float, float]
Store = Dict[Tuple[str, str], Deque[Candle]]


def main():
    cfg = load_config()
    exchange = make_exchange(cfg.exchange_id)

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

                    closed_records: List[Candle] = []
                    for row in raw[:-1]:
                        t_open_ms, o, h, l, c, *_ = row
                        t_close_ms = ts_close_from_open(int(t_open_ms), timeframe_sec)
                        closed_records.append(
                            (
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

                        # Falling Star
                        try:
                            analyze_falling_star(
                                symbol=symbol,
                                timeframe=timeframe,
                                t_close_ms=t_close_ms,
                                o=o, h=h, l=l, c=c,
                                cfg=cfg,
                            )
                        except Exception as e:
                            print(f"❌ {symbol} {timeframe}: ошибка в Falling Star — {e}")

                        # Hammer
                        try:
                            analyze_hammer(
                                symbol=symbol,
                                timeframe=timeframe,
                                t_close_ms=t_close_ms,
                                o=o, h=h, l=l, c=c,
                                cfg=cfg,
                            )
                        except Exception as e:
                            print(f"❌ {symbol} {timeframe}: ошибка в Hammer — {e}")

                        # Max_Volume_Zone
                        try:
                            analyze_max_volume_zone(
                                exchange=exchange,
                                symbol=symbol,
                                timeframe=timeframe,
                                candle_high=h,
                                candle_low=l,
                                candle_close_ts_ms=t_close_ms,
                                cfg=cfg,
                            )
                        except Exception as e:
                            print(
                                f"❌ {symbol} {timeframe}: ошибка в Max_Volume_Zone — {e}"
                            )

                        # RSI Zone Entry
                        try:
                            analyze_rsi_zone(
                                exchange=exchange,
                                symbol=symbol,
                                timeframe=timeframe,
                                candle_close_ts_ms=t_close_ms,
                                cfg=cfg,
                            )
                        except Exception as e:
                            print(f"❌ {symbol} {timeframe}: ошибка в RSI — {e}")

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


# notifier.py
import requests

def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    """
    Универсальная функция отправки сообщений в Telegram.
    Используется всеми сетапами и основным циклом.
    """
    if not token or not chat_id:
        print("⚠️ TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID пусты — пропускаю отправку")
        return

    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        r.raise_for_status()
    except Exception as e:
        print(f"❌ Ошибка отправки в Telegram: {e}")


# setups/falling_star.py
from datetime import datetime
from zoneinfo import ZoneInfo

from notifier import send_telegram_message


def is_falling_star(o: float, h: float, l: float, c: float) -> bool:
    """
    Упрощённые правила Falling Star:
      - тело мало: |o - c| <= 0.3 * (h - l)
      - верхняя тень большая: (h - max(o, c)) >= 0.6 * (h - l)
      - нижняя тень маленькая: (min(o, c) - l) <= 0.15 * (h - l)
    """
    range_high_low = max(h - l, 1e-12)
    body_size = abs(o - c)
    upper_shadow = h - max(o, c)
    lower_shadow = min(o, c) - l
    return (
        body_size <= 0.3 * range_high_low
        and upper_shadow >= 0.6 * range_high_low
        and lower_shadow <= 0.15 * range_high_low
    )


def analyze_falling_star(
    symbol: str,
    timeframe: str,
    t_close_ms: int,
    o: float,
    h: float,
    l: float,
    c: float,
    cfg,
) -> None:
    """
    Анализ закрытой свечи на Falling Star.
    """
    ts_str = datetime.fromtimestamp(t_close_ms / 1000, ZoneInfo(cfg.tz)).strftime("%Y-%m-%d %H:%M")

    if is_falling_star(o, h, l, c):
        message = f"{symbol} — Falling Star — {ts_str} ({timeframe})"
        print("ALERT:", message)
        send_telegram_message(cfg.tg_token, cfg.tg_chat_id, message)
    else:
        print(f"{symbol} {timeframe}: Falling Star — нет сигнала ({ts_str})")


# setups/hammer.py
from datetime import datetime
from zoneinfo import ZoneInfo

from notifier import send_telegram_message


def is_hammer(o: float, h: float, l: float, c: float) -> bool:
    """
    Зеркальная логика Falling Star:
    - маленькое тело
    - длинная нижняя тень
    - короткая верхняя тень
    """
    range_hl = max(h - l, 1e-12)
    body = abs(o - c)
    upper_shadow = h - max(o, c)
    lower_shadow = min(o, c) - l

    return (
        body <= 0.3 * range_hl and
        lower_shadow >= 0.6 * range_hl and
        upper_shadow <= 0.15 * range_hl
    )


def analyze_hammer(
    symbol: str,
    timeframe: str,
    t_close_ms: int,
    o: float,
    h: float,
    l: float,
    c: float,
    cfg,
) -> None:
    """
    Анализ закрытой свечи на предмет молота.
    Формат вывода — как у Falling Star.
    """
    ts_str = datetime.fromtimestamp(t_close_ms / 1000, ZoneInfo(cfg.tz)).strftime("%Y-%m-%d %H:%M")

    if is_hammer(o, h, l, c):
        msg = f"{symbol} — Hammer — {ts_str} ({timeframe})"
        print("ALERT:", msg)
        send_telegram_message(cfg.tg_token, cfg.tg_chat_id, msg)
    else:
        print(f"{symbol} {timeframe}: Hammer — нет сигнала ({ts_str})")


# setups/max_volume_zone.py
from datetime import datetime
from zoneinfo import ZoneInfo

import ccxt

from notifier import send_telegram_message


def tf_seconds(exchange: ccxt.Exchange, timeframe: str) -> int:
    return exchange.parse_timeframe(timeframe)


def now_local_str(tz_name: str) -> str:
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo as _ZoneInfo

    tz = _ZoneInfo(tz_name)
    dt = datetime.now(timezone.utc).astimezone(tz)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def analyze_max_volume_zone(
    exchange: ccxt.Exchange,
    symbol: str,
    timeframe: str,
    candle_high: float,
    candle_low: float,
    candle_close_ts_ms: int,
    cfg,
) -> None:
    """
    Max_Volume_Zone:
    - анализ только закрытой свечи TF
    - расчёт начала и конца свечи
    - вывод в стиле Falling Star
    """
    timeframe_sec = tf_seconds(exchange, timeframe)
    if timeframe_sec <= 0:
        return

    candle_open_ts_ms = candle_close_ts_ms - timeframe_sec * 1000

    tz = ZoneInfo(cfg.tz)
    dt_open = datetime.fromtimestamp(candle_open_ts_ms / 1000, tz)
    dt_close = datetime.fromtimestamp(candle_close_ts_ms / 1000, tz)

    open_str = dt_open.strftime("%Y-%m-%d %H:%M")
    close_str = dt_close.strftime("%Y-%m-%d %H:%M")

    price_range = candle_high - candle_low
    if price_range <= 0:
        print(f"{symbol} {timeframe}: Max_Volume_Zone — нет сигнала ({open_str}–{close_str})")
        return

    price_step = price_range / 5.0
    timeframe_sec = tf_seconds(exchange, timeframe)
    timeframe_minutes = timeframe_sec // 60
    minutes_limit = timeframe_minutes + 5

    try:
        raw_minutes = exchange.fetch_ohlcv(
            symbol,
            timeframe="1m",
            since=candle_open_ts_ms,
            limit=minutes_limit,
        )
    except Exception as e:
        print(f"❌ {symbol} {timeframe}: ошибка получения 1m — {e}")
        return

    if not raw_minutes:
        print(f"{symbol} {timeframe}: Max_Volume_Zone — нет минутных данных ({open_str}–{close_str})")
        return

    zone_volumes = [0.0] * 5

    for row in raw_minutes:
        if len(row) < 6:
            continue

        minute_open_ts_ms, o, h, l, c, vol = row[:6]

        if not (candle_open_ts_ms <= minute_open_ts_ms < candle_close_ts_ms):
            continue

        minute_high = float(h)
        minute_low = float(l)
        mid_price = (minute_high + minute_low) / 2.0

        distance_from_low = mid_price - candle_low
        if distance_from_low < 0 or distance_from_low > price_range:
            continue

        zone_index_from_bottom = int(distance_from_low // price_step)
        if zone_index_from_bottom >= 5:
            zone_index_from_bottom = 4

        zone_index_from_top = 4 - zone_index_from_bottom
        zone_volumes[zone_index_from_top] += float(vol)

    max_volume = max(zone_volumes)
    if max_volume <= 0:
        print(f"{symbol} {timeframe}: Max_Volume_Zone — нет сигнала ({open_str}–{close_str})")
        return

    max_zone_index = zone_volumes.index(max_volume)
    max_zone_number = max_zone_index + 1

    if max_zone_number == 1:
        direction = "bear"
    elif max_zone_number == 5:
        direction = "bull"
    else:
        print(f"{symbol} {timeframe}: Max_Volume_Zone — нет сигнала ({open_str}–{close_str})")
        return

    print(
        f"{symbol} {timeframe}: Max_Volume_Zone — {direction} "
        f"({open_str}–{close_str})"
    )

    message = (
        f"{symbol} — Max_Volume_Zone — {direction} — "
        f"{open_str}–{close_str} ({timeframe})\n"
        f"Signal time: {now_local_str(cfg.tz)}"
    )
    send_telegram_message(cfg.tg_token, cfg.tg_chat_id, message)


# setups/rsi_zone.py
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List

import ccxt

from notifier import send_telegram_message


def tf_seconds(exchange: ccxt.Exchange, timeframe: str) -> int:
    return exchange.parse_timeframe(timeframe)


def now_local_str(tz_name: str) -> str:
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo as _ZoneInfo

    tz = _ZoneInfo(tz_name)
    dt = datetime.now(timezone.utc).astimezone(tz)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def compute_rsi(closes: List[float], period: int = 14) -> float | None:
    """
    Расчёт RSI по формуле Wilder (RSI-14).
    """
    if len(closes) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(1, period + 1):
        diff = closes[-i] - closes[-i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(-diff)

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def analyze_rsi_zone(
    exchange: ccxt.Exchange,
    symbol: str,
    timeframe: str,
    candle_close_ts_ms: int,
    cfg,
) -> None:
    """
    Сетап RSI Zone Entry:
    - RSI <= 20 → oversold
    - RSI >= 80 → overbought
    - анализ только закрытой свечи
    """
    try:
        raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=100)
    except Exception as e:
        print(f"❌ {symbol} {timeframe}: ошибка получения OHLCV для RSI — {e}")
        return

    if not raw or len(raw) < 15:
        print(f"{symbol} {timeframe}: RSI — недостаточно данных")
        return

    timeframe_sec = tf_seconds(exchange, timeframe)

    closed_records = []
    for row in raw:
        t_open_ms, o, h, l, c, *_ = row
        t_close_ms = int(t_open_ms) + timeframe_sec * 1000
        if t_close_ms <= candle_close_ts_ms:
            closed_records.append((t_close_ms, o, h, l, c))

    if len(closed_records) < 15:
        print(f"{symbol} {timeframe}: RSI — мало закрытых свечей")
        return

    closed_records.sort(key=lambda x: x[0])

    if closed_records[-1][0] != candle_close_ts_ms:
        return

    closes = [c[4] for c in closed_records]
    rsi = compute_rsi(closes, period=14)
    if rsi is None:
        return

    candle_open_ts_ms = candle_close_ts_ms - timeframe_sec * 1000
    tz = ZoneInfo(cfg.tz)
    open_str = datetime.fromtimestamp(candle_open_ts_ms / 1000, tz).strftime("%Y-%m-%d %H:%M")
    close_str = datetime.fromtimestamp(candle_close_ts_ms / 1000, tz).strftime("%Y-%m-%d %H:%M")

    if rsi <= 20:
        direction = "oversold"
    elif rsi >= 80:
        direction = "overbought"
    else:
        print(f"{symbol} {timeframe}: RSI — нет сигнала ({open_str}–{close_str}) значение: {rsi:.2f}")
        return

    print(f"{symbol} {timeframe}: RSI — {direction} ({open_str}–{close_str}) значение: {rsi:.2f}")

    message = (
        f"{symbol} — RSI — {direction} — {open_str}–{close_str} ({timeframe})\n"
        f"RSI value: {rsi:.2f}\n"
        f"Signal time: {now_local_str(cfg.tz)}"
    )
    send_telegram_message(cfg.tg_token, cfg.tg_chat_id, message)


