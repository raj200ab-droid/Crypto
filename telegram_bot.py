import requests


def send_telegram_message(token, chat_id, message):
    if not token or not chat_id:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


def format_signal_message(symbol, signal, price, score, mtf_status=""):
    msg = f"{signal} signal: {symbol}\nScore: {score}/100\nPrice: {price}"
    if mtf_status:
        msg += f"\nMTF: {mtf_status}"
    return msg
