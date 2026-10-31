import re

from http_client import get_json

NEWS_URL = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN"

POSITIVE = ["surge", "rally", "bullish", "gain", "soar", "adopt", "approval", "approved",
            "record", "breakout", "partnership", "upgrade", "jump", "rise", "growth", "launch"]
NEGATIVE = ["crash", "bearish", "hack", "ban", "lawsuit", "plunge", "dump", "scam", "fraud",
            "exploit", "drop", "liquidation", "fall", "sue", "probe", "decline", "fear"]

NAMES = {
    "BTC": ["bitcoin"], "ETH": ["ethereum", "ether"], "BNB": ["binance coin"],
    "SOL": ["solana"], "XRP": ["ripple"], "ADA": ["cardano"], "DOGE": ["dogecoin"],
    "TRX": ["tron"], "AVAX": ["avalanche"], "DOT": ["polkadot"], "LINK": ["chainlink"],
    "LTC": ["litecoin"], "ZEC": ["zcash"], "SHIB": ["shiba"], "MATIC": ["polygon"],
}


def fetch_latest_news(limit=30):
    try:
        payload = get_json(NEWS_URL, timeout=10)
        if not isinstance(payload, dict):
            return []
        items = payload.get("Data", [])
        news = []
        for it in items[: int(limit)]:
            news.append({
                "title": it.get("title", ""),
                "body": it.get("body", ""),
                "categories": it.get("categories", ""),
            })
        return news
    except Exception:
        return []


def _score_text(text):
    text = text.lower()
    pos = sum(1 for w in POSITIVE if w in text)
    neg = sum(1 for w in NEGATIVE if w in text)
    return pos, neg


def get_sentiment_for_symbol(symbol, news_list):
    base = symbol[:-4] if symbol.endswith("USDT") else symbol
    names = NAMES.get(base, [])
    pattern = re.compile(r"\b" + re.escape(base) + r"\b", re.IGNORECASE)

    related = []
    for item in news_list or []:
        title = item.get("title", "")
        cats = item.get("categories", "")
        haystack = f"{title} {cats}"
        hit = bool(pattern.search(haystack)) or any(n in haystack.lower() for n in names)
        if hit:
            related.append(item)

    if not related:
        return 0.0, []

    total = 0.0
    for item in related:
        pos, neg = _score_text(item.get("title", ""))
        if pos + neg:
            total += (pos - neg) / (pos + neg)
    sentiment = max(-1.0, min(1.0, total / len(related)))
    return sentiment, [i.get("title", "") for i in related[:3]]
