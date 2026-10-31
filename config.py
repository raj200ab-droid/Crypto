import json
import os

DEFAULTS = {
    "dark_mode": True,
    "rsi_oversold": 30.0,
    "rsi_overbought": 70.0,
    "min_score_alert": 45.0,
    "top_n_coins": 40,
    "account_balance": 1000.0,
    "risk_percent": 2.0,
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "telegram_enabled": False,
    "paper_trading_enabled": True,
}


def get_data_dir():
    """Writable folder for settings and databases (works on Android and PC)."""
    base = os.environ.get("ANDROID_PRIVATE")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".cryptoscanner")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        base = os.getcwd()
    return base


def _settings_path():
    return os.path.join(get_data_dir(), "settings.json")


def load_settings():
    settings = dict(DEFAULTS)
    try:
        with open(_settings_path(), "r", encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            settings.update(saved)
    except Exception:
        pass
    return settings


def save_settings(settings):
    try:
        with open(_settings_path(), "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        print(f"Settings save error: {e}")
        return False
