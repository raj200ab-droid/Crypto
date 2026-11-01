"""Technical analysis in pure Python (no pandas / numpy needed)."""
import math

from config import load_settings


# ---------------- helpers ----------------
def _round_price(p):
    if p >= 100:
        return round(p, 2)
    if p >= 1:
        return round(p, 4)
    return round(p, 8)


def ema(values, period):
    if len(values) < period:
        return []
    k = 2.0 / (period + 1)
    out = [sum(values[:period]) / period]
    for v in values[period:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(closes, period=14):
    if len(closes) <= period:
        return None
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0)
        losses += max(-d, 0)
    avg_g = gains / period
    avg_l = losses / period
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        avg_g = (avg_g * (period - 1) + max(d, 0)) / period
        avg_l = (avg_l * (period - 1) + max(-d, 0)) / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100.0 - 100.0 / (1.0 + rs)


def atr(highs, lows, closes, period=14):
    if len(closes) <= period:
        return None
    trs = []
    for i in range(1, len(closes)):
        trs.append(max(highs[i] - lows[i],
                       abs(highs[i] - closes[i - 1]),
                       abs(lows[i] - closes[i - 1])))
    a = sum(trs[:period]) / period
    for tr in trs[period:]:
        a = (a * (period - 1) + tr) / period
    return a


def bollinger(closes, period=20, mult=2.0):
    if len(closes) < period:
        return None
    window = closes[-period:]
    mean = sum(window) / period
    var = sum((x - mean) ** 2 for x in window) / period
    std = var ** 0.5
    return mean - mult * std, mean, mean + mult * std


def macd_hist(closes):
    e12 = ema(closes, 12)
    e26 = ema(closes, 26)
    if not e26:
        return None
    n = len(e26)
    line = [a - b for a, b in zip(e12[-n:], e26)]
    sig = ema(line, 9)
    if len(sig) < 2:
        return None
    m = len(sig)
    return [l - s for l, s in zip(line[-m:], sig)]


# ---------------- scoring ----------------
def signal_from_scores(buy, sell):
    best = max(buy, sell)
    diff = abs(buy - sell)
    side = "BUY" if buy >= sell else "SELL"
    if best >= 70 and diff >= 15:
        return "STRONG_" + side
    if best >= 45 and diff >= 10:
        return side
    return "HOLD"


def refresh_result(result):
    """Recompute signal and reasons after the scores were changed."""
    result["buy_score"] = max(0, min(100, int(round(result["buy_score"]))))
    result["sell_score"] = max(0, min(100, int(round(result["sell_score"]))))
    result["signal"] = signal_from_scores(result["buy_score"], result["sell_score"])
    if result["buy_score"] >= result["sell_score"]:
        result["reasons"] = list(result.get("buy_reasons", []))
    else:
        result["reasons"] = list(result.get("sell_reasons", []))
    if not result["reasons"]:
        result["reasons"] = ["No strong reason"]
    return result


def analyze_symbol(df, news_sentiment=0.0):
    if not df or len(df) < 50:
        return None

    settings = load_settings()
    oversold = float(settings.get("rsi_oversold", 30))
    overbought = float(settings.get("rsi_overbought", 70))
    news_sentiment = news_sentiment or 0.0

    closes = [c["close"] for c in df]
    highs = [c["high"] for c in df]
    lows = [c["low"] for c in df]
    opens = [c["open"] for c in df]
    vols = [c["volume"] for c in df]
    price = closes[-1]

    r = rsi(closes)
    a = atr(highs, lows, closes)
    if r is None or a is None or price <= 0:
        return None

    buy = sell = 0
    buy_r, sell_r = [], []

    # RSI
    if r <= oversold:
        buy += 30
        buy_r.append(f"RSI oversold ({r:.1f})")
    elif r < 40:
        buy += 15
        buy_r.append(f"RSI low ({r:.1f})")
    if r >= overbought:
        sell += 30
        sell_r.append(f"RSI overbought ({r:.1f})")
    elif r > 60:
        sell += 15
        sell_r.append(f"RSI high ({r:.1f})")

    # MACD
    hist = macd_hist(closes)
    if hist:
        if hist[-1] > 0 and hist[-2] <= 0:
            buy += 25
            buy_r.append("MACD bullish cross")
        elif hist[-1] > 0 and hist[-1] > hist[-2]:
            buy += 10
            buy_r.append("MACD momentum up")
        if hist[-1] < 0 and hist[-2] >= 0:
            sell += 25
            sell_r.append("MACD bearish cross")
        elif hist[-1] < 0 and hist[-1] < hist[-2]:
            sell += 10
            sell_r.append("MACD momentum down")

    # Trend (EMA20 / EMA50)
    e20 = ema(closes, 20)
    e50 = ema(closes, 50)
    if e20 and e50:
        if e20[-1] > e50[-1] and price > e20[-1]:
            buy += 15
            buy_r.append("Uptrend (EMA20 > EMA50)")
        elif e20[-1] < e50[-1] and price < e20[-1]:
            sell += 15
            sell_r.append("Downtrend (EMA20 < EMA50)")

    # Bollinger bands
    bb = bollinger(closes)
    if bb:
        lower, _, upper = bb
        if price <= lower:
            buy += 15
            buy_r.append("Price at lower Bollinger band")
        elif price >= upper:
            sell += 15
            sell_r.append("Price at upper Bollinger band")

    # Volume spike
    if len(vols) >= 21:
        avg_vol = sum(vols[-21:-1]) / 20
        if avg_vol > 0 and vols[-1] > 1.5 * avg_vol:
            if closes[-1] >= opens[-1]:
                buy += 10
                buy_r.append("Volume spike (green candle)")
            else:
                sell += 10
                sell_r.append("Volume spike (red candle)")

    # News sentiment
    if news_sentiment > 0.3:
        buy += 10
        buy_r.append("Positive news")
    elif news_sentiment < -0.3:
        sell += 10
        sell_r.append("Negative news")

    result = {
        "price": _round_price(price),
        "rsi": round(r, 1),
        "atr": a,
        "buy_score": buy,
        "sell_score": sell,
        "buy_reasons": buy_r,
        "sell_reasons": sell_r,
        "mtf_status": "",
        "mtf_confirmed": None,
    }
    return refresh_result(result)


def suggest_exit_plan(price, atr_value, signal):
    if not atr_value or atr_value <= 0 or signal == "HOLD":
        return None
    if "BUY" in signal:
        sl = price - 1.5 * atr_value
        tp = price + 3.0 * atr_value
    else:
        sl = price + 1.5 * atr_value
        tp = price - 3.0 * atr_value
    if sl <= 0 or tp <= 0:
        return None
    return {
        "entry": _round_price(price),
        "stop_loss": _round_price(sl),
        "take_profit": _round_price(tp),
    }


def get_trend_direction(df):
    if not df or len(df) < 50:
        return "NEUTRAL"
    closes = [c["close"] for c in df]
    e20 = ema(closes, 20)
    e50 = ema(closes, 50)
    if not e20 or not e50:
        return "NEUTRAL"
    price = closes[-1]
    if price > e50[-1] and e20[-1] > e50[-1]:
        return "UP"
    if price < e50[-1] and e20[-1] < e50[-1]:
        return "DOWN"
    return "NEUTRAL"


def apply_mtf_confirmation(result, trend_direction):
    signal = result["signal"]
    if signal == "HOLD":
        result["mtf_status"] = "No signal"
        result["mtf_confirmed"] = None
        return result

    is_buy = "BUY" in signal
    if (is_buy and trend_direction == "UP") or (not is_buy and trend_direction == "DOWN"):
        result["mtf_status"] = f"Confirmed (higher TF {trend_direction})"
        result["mtf_confirmed"] = True
    elif (is_buy and trend_direction == "DOWN") or (not is_buy and trend_direction == "UP"):
        result["mtf_status"] = f"Conflict (higher TF {trend_direction})"
        result["mtf_confirmed"] = False
        if is_buy:
            result["buy_score"] -= 15
        else:
            result["sell_score"] -= 15
        refresh_result(result)
    else:
        result["mtf_status"] = "Higher TF neutral"
        result["mtf_confirmed"] = None
    return result


def project_future_candles(last_close, entry, take_profit, atr_value, n=12):
    """Scenario candles showing the path IF the trade works out (entry -> target).
    This is an illustration of the plan, NOT a prediction."""
    if not atr_value or atr_value <= 0 or take_profit <= entry:
        return []
    out = []
    prev = last_close
    for i in range(1, n + 1):
        close = entry + (take_profit - entry) * i / n
        if i < n:
            close += math.sin(i * 1.7) * 0.25 * atr_value
        high = max(prev, close) + 0.3 * atr_value
        low = max(min(prev, close) - 0.3 * atr_value, 0.0)
        out.append({"time": None, "open": prev, "high": high, "low": low,
                    "close": close, "volume": 0.0})
        prev = close
    return out
