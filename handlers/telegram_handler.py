# handlers/telegram_handler.py
from models import Signal
from notifier import send_telegram_message
from signal_formatter import format_signal


def make_telegram_handler(tg_token: str, tg_chat_id: str, tz: str):
    def handler(signal: Signal):
        text = format_signal(signal, tz)
        send_telegram_message(tg_token, tg_chat_id, text)
    return handler
