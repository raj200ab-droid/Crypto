import os
import sqlite3
import time

from config import get_data_dir


def _db_path():
    return os.path.join(get_data_dir(), "paper.db")


def _conn():
    return sqlite3.connect(_db_path())


def init_paper_db(starting_balance=1000.0):
    with _conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS account (id INTEGER PRIMARY KEY, balance REAL)")
        c.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT, signal_type TEXT,
                entry REAL, stop_loss REAL, take_profit REAL, qty REAL,
                status TEXT DEFAULT 'OPEN',
                close_price REAL, pnl REAL,
                opened_at REAL, closed_at REAL
            )
        """)
        row = c.execute("SELECT balance FROM account WHERE id=1").fetchone()
        if row is None:
            c.execute("INSERT INTO account (id, balance) VALUES (1, ?)", (float(starting_balance),))


def get_balance():
    with _conn() as c:
        row = c.execute("SELECT balance FROM account WHERE id=1").fetchone()
    return row[0] if row else 0.0


def open_paper_trade(symbol, signal_type, entry, stop_loss, take_profit, risk_percent=2.0):
    distance = abs(entry - stop_loss)
    if distance <= 0 or entry <= 0:
        return False
    with _conn() as c:
        exists = c.execute(
            "SELECT 1 FROM trades WHERE symbol=? AND status='OPEN'", (symbol,)
        ).fetchone()
        if exists:
            return False
        balance = c.execute("SELECT balance FROM account WHERE id=1").fetchone()[0]
        if balance <= 0:
            return False
        risk_amount = balance * float(risk_percent) / 100.0
        qty = risk_amount / distance
        if qty * entry > balance:
            qty = balance / entry  # no leverage
        c.execute(
            "INSERT INTO trades (symbol, signal_type, entry, stop_loss, take_profit, qty, opened_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (symbol, signal_type, entry, stop_loss, take_profit, qty, time.time()),
        )
    return True


def check_paper_trades(get_price):
    now = time.time()
    with _conn() as c:
        open_rows = c.execute(
            "SELECT id, symbol, signal_type, entry, stop_loss, take_profit, qty "
            "FROM trades WHERE status='OPEN'"
        ).fetchall()
        for tid, symbol, sig, entry, sl, tp, qty in open_rows:
            price = get_price(symbol)
            if price is None:
                continue
            is_buy = "BUY" in sig
            exit_price = None
            if is_buy:
                if price >= tp:
                    exit_price = tp
                elif price <= sl:
                    exit_price = sl
            else:
                if price <= tp:
                    exit_price = tp
                elif price >= sl:
                    exit_price = sl
            if exit_price is None:
                continue
            pnl = (exit_price - entry) * qty if is_buy else (entry - exit_price) * qty
            c.execute(
                "UPDATE trades SET status='CLOSED', close_price=?, pnl=?, closed_at=? WHERE id=?",
                (exit_price, pnl, now, tid),
            )
            c.execute("UPDATE account SET balance = balance + ? WHERE id=1", (pnl,))


def get_open_trades():
    with _conn() as c:
        return c.execute(
            "SELECT symbol, signal_type, entry, qty FROM trades WHERE status='OPEN' ORDER BY id DESC"
        ).fetchall()


def get_paper_trade_history(limit=15):
    with _conn() as c:
        return c.execute(
            "SELECT symbol, signal_type, entry, close_price, pnl FROM trades "
            "WHERE status='CLOSED' ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
