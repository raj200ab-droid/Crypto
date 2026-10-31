from kivy.graphics import Color, Line, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

MAX_CANDLES = 60


class _CandleCanvas(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.candles = []
        self.bind(pos=self.redraw, size=self.redraw)

    def set_candles(self, candles):
        self.candles = candles[-MAX_CANDLES:]
        self.redraw()

    def redraw(self, *args):
        self.canvas.clear()
        with self.canvas:
            Color(0.08, 0.08, 0.1, 1)
            Rectangle(pos=self.pos, size=self.size)

            if not self.candles or self.width <= 0 or self.height <= 0:
                return

            lo = min(c["low"] for c in self.candles)
            hi = max(c["high"] for c in self.candles)
            span = (hi - lo) or 1.0
            pad = 10
            h = self.height - 2 * pad
            slot = (self.width - 2 * pad) / len(self.candles)
            body_w = max(1.0, slot * 0.7)

            def y(price):
                return self.y + pad + (price - lo) / span * h

            for i, c in enumerate(self.candles):
                x_center = self.x + pad + slot * (i + 0.5)
                green = c["close"] >= c["open"]
                Color(0.15, 0.75, 0.4, 1) if green else Color(0.9, 0.25, 0.3, 1)
                Line(points=[x_center, y(c["low"]), x_center, y(c["high"])], width=1)
                top = y(max(c["open"], c["close"]))
                bottom = y(min(c["open"], c["close"]))
                Rectangle(pos=(x_center - body_w / 2, bottom),
                          size=(body_w, max(1.0, top - bottom)))


class ChartView(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.title = Label(text="Select a coin and press Load Chart",
                           size_hint_y=None, height=30, font_size=13)
        self.canvas_widget = _CandleCanvas()
        self.add_widget(self.title)
        self.add_widget(self.canvas_widget)

    def show_chart(self, symbol, df, timeframe):
        if not df:
            self.title.text = f"{symbol}: no data"
            return
        last = df[-1]["close"]
        self.title.text = f"{symbol}  [{timeframe}]  Last: {last}"
        self.canvas_widget.set_candles(df)
