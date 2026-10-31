import os
import sqlite3
import time

from config import get_data_dir


def _db_path():
    return os.path.join(get_data_dir(), "signals.db")


def _conn():
    return sqlite3.connect(_db_path())


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT, timeframe TEXT, signal_type TEXT,
                entry_price REAL, stop_loss REAL, take_profit REAL, score REAL,
                status TEXT DEFAULT 'PENDING',
                created_at REAL, closed_at REAL,
                close_price REAL, profit_percent REAL
            )
        """)


def _direction(signal_type):
    return "BUY" if "BUY" in signal_type else "SELL"


def save_signal(symbol, timeframe, signal_type, entry, stop_loss, take_profit, score):
    direction = _direction(signal_type)
    with _conn() as c:
        rows = c.execute(
            "SELECT signal_type FROM signals WHERE symbol=? AND timeframe=? AND status='PENDING'",
            (symbol, timeframe),
        ).fetchall()
        for (existing,) in rows:
            if _direction(existing) == direction:
                return False  # already tracking this one
        c.execute(
            "INSERT INTO signals (symbol, timeframe, signal_type, entry_price, stop_loss, take_profit, score, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (symbol, timeframe, signal_type, entry, stop_loss, take_profit, score, time.time()),
        )
    return True


def _profit_percent(signal_type, entry, exit_price):
    if not entry:
        return 0.0
    change = (exit_price - entry) / entry * 100.0
    return change if _direction(signal_type) == "BUY" else -change


def check_pending_signals(get_price, expiry_days=7):
    now = time.time()
    with _conn() as c:
        pending = c.execute(
            "SELECT id, symbol, signal_type, entry_price, stop_loss, take_profit, created_at "
            "FROM signals WHERE status='PENDING'"
        ).fetchall()
        for sid, symbol, sig, entry, sl, tp, created in pending:
            price = get_price(symbol)
            if price is None:
                continue
            is_buy = _direction(sig) == "BUY"
            status = None
            exit_price = price
            if is_buy:
                if price >= tp:
                    status, exit_price = "WIN", tp
                elif price <= sl:
                    status, exit_price = "LOSS", sl
            else:
                if price <= tp:
                    status, exit_price = "WIN", tp
                elif price >= sl:
                    status, exit_price = "LOSS", sl
            if status is None and now - created > expiry_days * 86400:
                status = "EXPIRED"
            if status:
                c.execute(
                    "UPDATE signals SET status=?, closed_at=?, close_price=?, profit_percent=? WHERE id=?",
                    (status, now, exit_price, _profit_percent(sig, entry, exit_price), sid),
                )


def get_stats():
    with _conn() as c:
        wins = c.execute("SELECT COUNT(*) FROM signals WHERE status='WIN'").fetchone()[0]
        losses = c.execute("SELECT COUNT(*) FROM signals WHERE status='LOSS'").fetchone()[0]
        avg = c.execute(
            "SELECT AVG(profit_percent) FROM signals WHERE status IN ('WIN','LOSS')"
        ).fetchone()[0]
    total = wins + losses
    return {
        "total_closed": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / total * 100, 1) if total else 0.0,
        "avg_profit_percent": round(avg, 2) if avg is not None else 0.0,
    }


def get_pending_count():
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM signals WHERE status='PENDING'").fetchone()[0]


def get_recent_history(limit=15):
    with _conn() as c:
        return c.execute(
            "SELECT symbol, timeframe, signal_type, status, profit_percent, closed_at "
            "FROM signals ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
