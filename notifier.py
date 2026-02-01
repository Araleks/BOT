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
