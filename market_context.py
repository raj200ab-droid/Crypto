from http_client import get_json
from binance_data import get_klines
from strategy import get_trend_direction, refresh_result


def get_btc_trend():
    df = get_klines("BTCUSDT", interval="4h", limit=100)
    return get_trend_direction(df)


def get_fear_greed_index():
    try:
        data = get_json("https://api.alternative.me/fng/?limit=1", timeout=10)
        return int(data["data"][0]["value"])
    except Exception:
        return None


def apply_market_context_filter(result, symbol, btc_trend, fear_greed):
    notes = []
    signal = result.get("signal", "HOLD")

    if signal != "HOLD":
        is_buy = "BUY" in signal

        if symbol != "BTCUSDT":
            if is_buy and btc_trend == "DOWN":
                result["buy_score"] -= 10
                notes.append("BTC downtrend (-10)")
            elif (not is_buy) and btc_trend == "UP":
                result["sell_score"] -= 10
                notes.append("BTC uptrend (-10)")
            elif (is_buy and btc_trend == "UP") or ((not is_buy) and btc_trend == "DOWN"):
                notes.append(f"BTC {btc_trend} agrees")

        if fear_greed is not None:
            if fear_greed <= 25:
                notes.append(f"Extreme fear ({fear_greed})")
                if is_buy:
                    result["buy_score"] += 5
            elif fear_greed >= 75:
                notes.append(f"Extreme greed ({fear_greed})")
                if is_buy:
                    result["buy_score"] -= 5
                else:
                    result["sell_score"] += 5

        refresh_result(result)

    result["market_context_note"] = "; ".join(notes) if notes else "Neutral"
    return result
