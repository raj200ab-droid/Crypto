import os, sys, tempfile, traceback, random
os.environ["ANDROID_PRIVATE"] = tempfile.mkdtemp()
os.environ["KIVY_NO_ARGS"] = "1"
sys.path.insert(0, os.getcwd())

def fail(title, text):
    print("\n" + "=" * 60 + "\nSMOKE TEST FAILED: " + title + "\n" + "=" * 60 + "\n" + text)
    sys.exit(1)

try:
    import main
except Exception:
    fail("import main", traceback.format_exc())
if main.IMPORT_ERROR:
    fail("project import", main.IMPORT_ERROR)

try:
    app = main.CryptoScannerApp()
    root = app.build()
except Exception:
    fail("build()", traceback.format_exc())
if isinstance(root, main.ScrollView):
    fail("build() returned error screen", root.children[0].text)

from kivy.base import EventLoop
from kivy.core.window import Window
try:
    EventLoop.ensure_window()
    Window.add_widget(root)
    for _ in range(10):
        EventLoop.idle()
except Exception:
    fail("rendering first frames", traceback.format_exc())

try:
    random.seed(1)
    p, candles = 100.0, []
    for i in range(100):
        o = p
        p = p * (1 + random.gauss(0, 0.01))
        candles.append({"time": i, "open": o, "high": max(o, p) * 1.003,
                        "low": min(o, p) * 0.997, "close": p, "volume": 1000.0})
    app.chart_view.show_chart("TESTUSDT", candles, "1h")
    for _ in range(5):
        EventLoop.idle()
    app.update_stats_view()
    app.update_paper_view()
    fake = {"symbol": "TESTUSDT", "signal": "BUY", "buy_score": 80, "sell_score": 10,
            "price": 100.0, "rsi": 25.0, "atr": 2.0, "reasons": ["test"],
            "mtf_status": "ok", "market_context_note": "ok",
            "candles": candles[-40:]}
    app.display_results([fake])
    assert len(app.result_layout.children) == 1, "BUY card missing"
    card = app.result_layout.children[0]
    assert len(card.children) == 3, "card should have text + chart + caption"
    for _ in range(5):
        EventLoop.idle()
except Exception:
    fail("screens / chart / signal card", traceback.format_exc())

print("SMOKE TEST PASSED")
