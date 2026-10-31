def calculate_position_size(balance, risk_percent, entry, stop_loss):
    """Position size so that hitting the stop loss loses risk_percent of balance."""
    try:
        balance = float(balance)
        risk_percent = float(risk_percent)
        entry = float(entry)
        stop_loss = float(stop_loss)
    except (TypeError, ValueError):
        return None

    if balance <= 0 or risk_percent <= 0 or entry <= 0:
        return None
    distance = abs(entry - stop_loss)
    if distance <= 0:
        return None

    risk_amount = balance * risk_percent / 100.0
    position_usd = risk_amount / (distance / entry)
    position_usd = min(position_usd, balance)  # no leverage
    return {
        "position_size_usd": round(position_usd, 2),
        "risk_amount": round(risk_amount, 2),
        "quantity": position_usd / entry,
    }
