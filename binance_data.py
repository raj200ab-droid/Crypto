from http_client import get_json

BASES = [
    "https://api.binance.com",
    "https://data-api.binance.vision",
    "https://api1.binance.com",
]
_working_base = {"url": None}

STABLE_BASES = {"USDC", "FDUSD", "TUSD", "BUSD", "USDP", "DAI", "USDT", "EUR", "AEUR", "UST", "USD1", "XUSD"}
LEVERAGED_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR")

TREND_TIMEFRAMES = {"15m": "1h", "1h": "4h", "4h": "1d", "1d": "1w"}


def _get(path, params=None):
    bases = list(BASES)
    if _working_base["url"] in bases:
        bases.remove(_working_base["url"])
        bases.insert(0, _working_base["url"])
    for base in bases:
        data = get_json(base + path, params=params, timeout=10)
        if data is not None:
            _working_base["url"] = base
            return data
    return None


def get_top_symbols(limit=40):
    data = _get("/api/v3/ticker/24hr")
    if not data:
        return []
    pairs = []
    for item in data:
        sym = item.get("symbol", "")
        if not sym.endswith("USDT"):
            continue
        base = sym[:-4]
        if base in STABLE_BASES or base.endswith(LEVERAGED_SUFFIXES):
            continue
        try:
            pairs.append((sym, float(item.get("quoteVolume", 0))))
        except (TypeError, ValueError):
            continue
    pairs.sort(key=lambda x: x[1], reverse=True)
    return [s for s, _ in pairs[: int(limit)]]


def get_klines(symbol, interval="1h", limit=100):
    """Returns a list of candle dicts (oldest first) or None."""
    data = _get("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": int(limit)})
    if not data or not isinstance(data, list) or len(data) < 30:
        return None
    candles = []
    try:
        for k in data:
            candles.append({
                "time": int(k[0]),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            })
    except (TypeError, ValueError, IndexError):
        return None
    return candles


def get_trend_timeframe(timeframe):
    return TREND_TIMEFRAMES.get(timeframe, "4h")


def get_current_price(symbol):
    data = _get("/api/v3/ticker/price", {"symbol": symbol})
    try:
        return float(data["price"])
    except Exception:
        return None
