from kivy.graphics import Color, Line, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

MAX_CANDLES = 60

GREEN = (0.15, 0.75, 0.4, 1)
RED = (0.9, 0.25, 0.3, 1)
BLUE = (0.25, 0.55, 1.0, 1)
WHITE = (0.85, 0.85, 0.85, 1)


class CandleCanvas(Widget):
    """Candle chart: real candles (green/red), optional future scenario candles
    (blue) and horizontal price lines (entry / target / stop-loss)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.candles = []
        self.future = []
        self.levels = []
        self.max_real = MAX_CANDLES
        self.bind(pos=self.redraw, size=self.redraw)

    def set_candles(self, candles):
        self.set_data(candles)

    def set_data(self, candles, future=None, levels=None, max_real=MAX_CANDLES):
        self.max_real = max_real
        self.candles = list(candles or [])[-max_real:]
        self.future = list(future or [])
        self.levels = list(levels or [])
        self.redraw()

    def redraw(self, *args):
        self.canvas.clear()
        with self.canvas:
            Color(0.08, 0.08, 0.1, 1)
            Rectangle(pos=self.pos, size=self.size)

            allc = self.candles + self.future
            if not allc or self.width <= 0 or self.height <= 0:
                return

            lows = [c["low"] for c in allc] + [p for p, _ in self.levels]
            highs = [c["high"] for c in allc] + [p for p, _ in self.levels]
            lo, hi = min(lows), max(highs)
            span = (hi - lo) or 1.0
            pad = 8
            h = self.height - 2 * pad
            slot = (self.width - 2 * pad) / len(allc)
            body_w = max(1.0, slot * 0.7)

            def y(price):
                return self.y + pad + (price - lo) / span * h

            # price lines (entry / target / stop)
            for price, color in self.levels:
                Color(*color)
                Line(points=[self.x + pad, y(price), self.x + self.width - pad, y(price)],
                     width=1, dash_length=5, dash_offset=4)

            # separator between real and future candles
            if self.future and self.candles:
                xs = self.x + pad + slot * len(self.candles)
                Color(0.5, 0.5, 0.5, 1)
                Line(points=[xs, self.y + pad, xs, self.y + self.height - pad], width=1)

            for i, c in enumerate(allc):
                is_future = i >= len(self.candles)
                x_center = self.x + pad + slot * (i + 0.5)
                if is_future:
                    Color(*BLUE)
                else:
                    Color(*(GREEN if c["close"] >= c["open"] else RED))
                Line(points=[x_center, y(c["low"]), x_center, y(c["high"])], width=1)
                top = y(max(c["open"], c["close"]))
                bottom = y(min(c["open"], c["close"]))
                Rectangle(pos=(x_center - body_w / 2, bottom),
                          size=(body_w, max(1.0, top - bottom)))


# kept for older imports
_CandleCanvas = CandleCanvas


class ChartView(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.title = Label(text="Select a coin and press Load Chart",
                           size_hint_y=None, height=30, font_size=13)
        self.canvas_widget = CandleCanvas()
        self.add_widget(self.title)
        self.add_widget(self.canvas_widget)

    def show_chart(self, symbol, df, timeframe, future=None, levels=None):
        if not df:
            self.title.text = f"{symbol}: no data"
            return
        last = df[-1]["close"]
        self.title.text = f"{symbol}  [{timeframe}]  Last: {last}"
        self.canvas_widget.set_data(df, future=future, levels=levels)
