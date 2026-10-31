from kivy.app import App
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button, ToggleButton
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.clock import Clock

from binance_data import get_top_symbols, get_klines, get_trend_timeframe, get_current_price
from strategy import analyze_symbol, suggest_exit_plan, get_trend_direction, apply_mtf_confirmation
from news import fetch_latest_news, get_sentiment_for_symbol
from tracker import init_db, save_signal, check_pending_signals, get_stats, get_pending_count, get_recent_history
from config import load_settings, save_settings
from telegram_bot import send_telegram_message, format_signal_message
from risk_calculator import calculate_position_size
from market_context import get_btc_trend, get_fear_greed_index, apply_market_context_filter
from chart_widget import ChartView
from paper_trading import (init_paper_db, open_paper_trade, check_paper_trades,
                            get_balance, get_open_trades, get_paper_trade_history)

try:
    from plyer import notification
    NOTIFICATIONS_AVAILABLE = True
except Exception:
    NOTIFICATIONS_AVAILABLE = False

TIMEFRAME_INTERVALS = {"15m": 120, "1h": 300, "4h": 900, "1d": 3600}
TRACK_CHECK_INTERVAL = 180


class CryptoScannerApp(App):
    def build(self):
        self.title = "Crypto Signal Scanner Pro"
        self.settings = load_settings()
        self.last_signals = {}
        self.current_timeframe = "1h"
        self.mtf_confirm_enabled = True
        self.refresh_event = None
        self.last_scan_results = []   # filter/sort এর জন্য cache
        self.filter_mode = "All"
        self.sort_mode = "Score"
        self.btc_trend = "NEUTRAL"
        self.fear_greed = None

        init_db()
        init_paper_db(starting_balance=self.settings.get("account_balance", 1000.0))

        self.apply_theme()

        root = BoxLayout(orientation="vertical")

        # ---- Top control bar ----
        control_bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=50, spacing=5, padding=5)
        control_bar.add_widget(Label(text="TF:", size_hint_x=0.12, **self.label_kwargs()))

        self.tf_spinner = Spinner(text=self.current_timeframe, values=["15m", "1h", "4h", "1d"], size_hint_x=0.2)
        self.tf_spinner.bind(text=self.on_timeframe_change)
        control_bar.add_widget(self.tf_spinner)

        self.mtf_toggle = ToggleButton(text="MTF: ON", state="down", size_hint_x=0.25)
        self.mtf_toggle.bind(on_press=self.on_mtf_toggle)
        control_bar.add_widget(self.mtf_toggle)

        self.dark_toggle = ToggleButton(text="🌙", state="down" if self.settings["dark_mode"] else "normal", size_hint_x=0.13)
        self.dark_toggle.bind(on_press=self.on_dark_toggle)
        control_bar.add_widget(self.dark_toggle)

        refresh_btn = Button(text="Refresh", size_hint_x=0.3)
        refresh_btn.bind(on_press=lambda x: self.scan_market())
        control_bar.add_widget(refresh_btn)

        root.add_widget(control_bar)

        self.header = Label(text="Ready...", size_hint_y=None, height=30, font_size=13, **self.label_kwargs())
        root.add_widget(self.header)

        # ---- Tabs ----
        self.tabs = TabbedPanel(do_default_tab=False)

        # Tab 1: Live Signals
        signals_tab = TabbedPanelItem(text="Signals")
        signals_container = BoxLayout(orientation="vertical")

        filter_bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=45, spacing=5, padding=5)
        self.filter_spinner = Spinner(text="All", values=["All", "BUY Only", "SELL Only", "Strong Only"], size_hint_x=0.5)
        self.filter_spinner.bind(text=self.on_filter_change)
        filter_bar.add_widget(self.filter_spinner)

        self.sort_spinner = Spinner(text="Score", values=["Score", "Symbol", "RSI"], size_hint_x=0.5)
        self.sort_spinner.bind(text=self.on_sort_change)
        filter_bar.add_widget(self.sort_spinner)

        signals_container.add_widget(filter_bar)

        self.scroll = ScrollView()
        self.result_layout = BoxLayout(orientation="vertical", size_hint_y=None, spacing=10, padding=10)
        self.result_layout.bind(minimum_height=self.result_layout.setter("height"))
        self.scroll.add_widget(self.result_layout)
        signals_container.add_widget(self.scroll)

        signals_tab.add_widget(signals_container)
        self.tabs.add_widget(signals_tab)

        # Tab 2: Chart
        chart_tab = TabbedPanelItem(text="Chart")
        chart_container = BoxLayout(orientation="vertical")
        chart_control = BoxLayout(orientation="horizontal", size_hint_y=None, height=45, spacing=5, padding=5)
        self.chart_symbol_spinner = Spinner(text="BTCUSDT", values=["BTCUSDT"], size_hint_x=0.6)
        chart_control.add_widget(self.chart_symbol_spinner)
        load_chart_btn = Button(text="Load Chart", size_hint_x=0.4)
        load_chart_btn.bind(on_press=lambda x: self.load_chart())
        chart_control.add_widget(load_chart_btn)
        chart_container.add_widget(chart_control)
        self.chart_view = ChartView()
        chart_container.add_widget(self.chart_view)
        chart_tab.add_widget(chart_container)
        self.tabs.add_widget(chart_tab)

        # Tab 3: Performance
        stats_tab = TabbedPanelItem(text="Performance")
        self.stats_scroll = ScrollView()
        self.stats_layout = BoxLayout(orientation="vertical", size_hint_y=None, spacing=10, padding=10)
        self.stats_layout.bind(minimum_height=self.stats_layout.setter("height"))
        self.stats_scroll.add_widget(self.stats_layout)
        stats_tab.add_widget(self.stats_scroll)
        stats_tab.bind(on_release=lambda x: self.update_stats_view())
        self.tabs.add_widget(stats_tab)

        # Tab 4: Paper Trading
        paper_tab = TabbedPanelItem(text="Paper Trade")
        self.paper_scroll = ScrollView()
        self.paper_layout = BoxLayout(orientation="vertical", size_hint_y=None, spacing=10, padding=10)
        self.paper_layout.bind(minimum_height=self.paper_layout.setter("height"))
        self.paper_scroll.add_widget(self.paper_layout)
        paper_tab.add_widget(self.paper_scroll)
        paper_tab.bind(on_release=lambda x: self.update_paper_view())
        self.tabs.add_widget(paper_tab)

        # Tab 5: Settings
        settings_tab = TabbedPanelItem(text="Settings")
        self.build_settings_tab(settings_tab)
        self.tabs.add_widget(settings_tab)

        root.add_widget(self.tabs)

        Clock.schedule_once(lambda dt: self.scan_market(), 1)
        self.schedule_auto_refresh()
        Clock.schedule_interval(lambda dt: self.update_tracking(), TRACK_CHECK_INTERVAL)
        Clock.schedule_once(lambda dt: self.update_tracking(), 5)

        return root

    # ---------------- THEME ----------------
    def apply_theme(self):
        if self.settings.get("dark_mode", True):
            Window.clearcolor = (0.1, 0.1, 0.1, 1)
        else:
            Window.clearcolor = (1, 1, 1, 1)

    def label_kwargs(self):
        color = (1, 1, 1, 1) if self.settings.get("dark_mode", True) else (0, 0, 0, 1)
        return {"color": color}

    def on_dark_toggle(self, instance):
        Clock.schedule_once(lambda dt: self._toggle_dark(), 0.05)

    def _toggle_dark(self):
        self.settings["dark_mode"] = self.dark_toggle.state == "down"
        save_settings(self.settings)
        self.apply_theme()
        self.header.text = "Theme changed. Restart app for full effect."

    # ---------------- FILTER / SORT ----------------
    def on_filter_change(self, spinner, value):
        self.filter_mode = value
        self.display_results(self.last_scan_results)

    def on_sort_change(self, spinner, value):
        self.sort_mode = value
        self.display_results(self.last_scan_results)

    def apply_filter_sort(self, signals):
        filtered = signals
        if self.filter_mode == "BUY Only":
            filtered = [s for s in signals if "BUY" in s["signal"]]
        elif self.filter_mode == "SELL Only":
            filtered = [s for s in signals if "SELL" in s["signal"]]
        elif self.filter_mode == "Strong Only":
            filtered = [s for s in signals if "STRONG" in s["signal"]]

        if self.sort_mode == "Score":
            filtered = sorted(filtered, key=lambda x: max(x["buy_score"], x["sell_score"]), reverse=True)
        elif self.sort_mode == "Symbol":
            filtered = sorted(filtered, key=lambda x: x["symbol"])
        elif self.sort_mode == "RSI":
            filtered = sorted(filtered, key=lambda x: x["rsi"])

        return filtered

    # ---------------- TIMEFRAME / MTF ----------------
    def on_timeframe_change(self, spinner, new_timeframe):
        self.current_timeframe = new_timeframe
        self.last_signals = {}
        self.scan_market()
        self.schedule_auto_refresh()

    def on_mtf_toggle(self, instance):
        Clock.schedule_once(lambda dt: self.update_mtf_state(), 0.05)

    def update_mtf_state(self):
        self.mtf_confirm_enabled = self.mtf_toggle.state == "down"
        self.mtf_toggle.text = "MTF: ON" if self.mtf_confirm_enabled else "MTF: OFF"
        self.scan_market()

    def schedule_auto_refresh(self):
        if self.refresh_event:
            self.refresh_event.cancel()
        interval = TIMEFRAME_INTERVALS.get(self.current_timeframe, 300)
        self.refresh_event = Clock.schedule_interval(lambda dt: self.scan_market(), interval)

    # ---------------- TRACKING ----------------
    def update_tracking(self):
        try:
            check_pending_signals(get_current_price, expiry_days=7)
            if self.settings.get("paper_trading_enabled", True):
                check_paper_trades(get_current_price)
        except Exception as e:
            print(f"Tracking error: {e}")

    # ---------------- CHART ----------------
    def load_chart(self):
        symbol = self.chart_symbol_spinner.text
        df = get_klines(symbol, interval=self.current_timeframe, limit=100)
        if df is not None:
            self.chart_view.show_chart(symbol, df, self.current_timeframe)

    # ---------------- MAIN SCAN ----------------
    def scan_market(self):
        self.result_layout.clear_widgets()
        timeframe = self.current_timeframe
        self.header.text = f"[{timeframe}] Fetching market context..."

        self.btc_trend = get_btc_trend()
        self.fear_greed = get_fear_greed_index()
        news_list = fetch_latest_news(limit=30)

        self.header.text = f"[{timeframe}] Finding top coins..."
        top_n = self.settings.get("top_n_coins", 40)
        symbols = get_top_symbols(limit=top_n)

        if not symbols:
            self.header.text = "Error: Could not fetch symbols (check internet)"
            return

        self.chart_symbol_spinner.values = symbols
        trend_timeframe = get_trend_timeframe(timeframe)
        self.header.text = f"[{timeframe}] Analyzing {len(symbols)} coins..."

        signals_found = []

        for symbol in symbols:
            df_entry = get_klines(symbol, interval=timeframe, limit=100)
            if df_entry is None:
                continue

            sentiment, related_news = get_sentiment_for_symbol(symbol, news_list)
            result = analyze_symbol(df_entry, news_sentiment=sentiment)
            if result is None:
                continue

            if self.mtf_confirm_enabled:
                df_trend = get_klines(symbol, interval=trend_timeframe, limit=100)
                trend_direction = get_trend_direction(df_trend)
                result = apply_mtf_confirmation(result, trend_direction)
                result["trend_tf"] = trend_timeframe
            else:
                result["mtf_status"] = "MTF Disabled"

            # Market context (BTC correlation + Fear&Greed)
            result = apply_market_context_filter(result, symbol, self.btc_trend, self.fear_greed)

            if result["signal"] != "HOLD":
                result["symbol"] = symbol
                result["news"] = related_news
                signals_found.append(result)

                if result["signal"] in ["BUY", "STRONG_BUY", "SELL", "STRONG_SELL"]:
                    exit_plan = suggest_exit_plan(result["price"], result["atr"], result["signal"])
                    if exit_plan:
                        save_signal(symbol, timeframe, result["signal"], result["price"],
                                    exit_plan["stop_loss"], exit_plan["take_profit"],
                                    max(result["buy_score"], result["sell_score"]))

                        if self.settings.get("paper_trading_enabled", True) and "BUY" in result["signal"]:
                            open_paper_trade(symbol, result["signal"], result["price"],
                                              exit_plan["stop_loss"], exit_plan["take_profit"],
                                              self.settings.get("risk_percent", 2.0))

        self.last_scan_results = signals_found
        self.header.text = f"[{timeframe}] Scan Complete - {len(signals_found)} signals | BTC: {self.btc_trend}"
        self.display_results(signals_found)

    # ---------------- DISPLAY ----------------
    def display_results(self, signals):
        self.result_layout.clear_widgets()
        filtered = self.apply_filter_sort(signals)

        if not filtered:
            self.result_layout.add_widget(Label(text="No signals match filter.", size_hint_y=None, height=50, **self.label_kwargs()))
            return

        for result in filtered:
            symbol = result["symbol"]
            signal = result["signal"]
            score = max(result["buy_score"], result["sell_score"])

            card_text = (
                f"[b]{symbol}[/b]  |  Score: {score}/100  |  TF: {self.current_timeframe}\n"
                f"Price: {result['price']}  |  RSI: {result['rsi']}\n"
                f"Signal: [b]{signal}[/b]\n"
            )

            if self.mtf_confirm_enabled:
                card_text += f"MTF: {result.get('mtf_status', '')}\n"

            card_text += f"Market: {result.get('market_context_note', '')}\n"
            card_text += f"Reasons: {', '.join(result['reasons'])}\n"

            if signal in ["BUY", "STRONG_BUY"]:
                exit_plan = suggest_exit_plan(result["price"], result["atr"], signal)
                card_text += f"Entry: {exit_plan['entry']} | SL: {exit_plan['stop_loss']} | TP: {exit_plan['take_profit']}\n"

                pos_info = calculate_position_size(
                    self.settings.get("account_balance", 1000.0),
                    self.settings.get("risk_percent", 2.0),
                    result["price"], exit_plan["stop_loss"]
                )
                if pos_info:
                    card_text += f"Suggested Size: ${pos_info['position_size_usd']} (risking ${pos_info['risk_amount']})\n"

            label = Label(text=card_text, markup=True, size_hint_y=None, height=230,
                          halign="left", valign="top", **self.label_kwargs())
            label.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            self.result_layout.add_widget(label)

            signal_key = f"{symbol}_{self.current_timeframe}"
            prev_signal = self.last_signals.get(signal_key)
            should_notify = score >= self.settings.get("min_score_alert", 45) and signal != prev_signal
            if self.mtf_confirm_enabled and result.get("mtf_confirmed") is False:
                should_notify = False

            if should_notify:
                self.send_notification(symbol, signal, result["price"], score, result.get("mtf_status", ""))

            self.last_signals[signal_key] = signal

    # ---------------- NOTIFICATIONS ----------------
    def send_notification(self, symbol, signal, price, score, mtf_status=""):
        if NOTIFICATIONS_AVAILABLE:
            try:
                notification.notify(title=f"{signal} ({score}/100): {symbol}", message=f"Price: {price}", timeout=10)
            except Exception as e:
                print(f"Notification error: {e}")

        if self.settings.get("telegram_enabled", False):
            msg = format_signal_message(symbol, signal, price, score, mtf_status)
            send_telegram_message(self.settings.get("telegram_bot_token"), self.settings.get("telegram_chat_id"), msg)

        print(f"[ALERT] {symbol} -> {signal} ({score}/100) at {price}")

    # ---------------- PERFORMANCE TAB ----------------
    def update_stats_view(self):
        self.stats_layout.clear_widgets()
        overall = get_stats()
        pending_count = get_pending_count()

        summary_text = (
            f"[b][size=18]Overall Performance[/size][/b]\n\n"
            f"Total Closed: {overall['total_closed']}\n"
            f"✅ Wins: {overall['wins']}   ❌ Losses: {overall['losses']}\n"
            f"[b]Win Rate: {overall['win_rate']}%[/b]\n"
            f"Avg Profit/Trade: {overall['avg_profit_percent']}%\n"
            f"Pending: {pending_count}\n"
        )
        summary = Label(text=summary_text, markup=True, size_hint_y=None, height=180,
                        halign="left", valign="top", **self.label_kwargs())
        summary.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        self.stats_layout.add_widget(summary)

        for symbol, tf, sig_type, status, profit, closed_at in get_recent_history(15):
            icon = "✅" if status == "WIN" else ("❌" if status == "LOSS" else "⌛")
            profit_str = f"{profit:+.2f}%" if profit is not None else "N/A"
            text = f"{icon} {symbol} [{tf}] {sig_type} -> {status} ({profit_str})"
            item = Label(text=text, size_hint_y=None, height=28, halign="left", **self.label_kwargs())
            item.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            self.stats_layout.add_widget(item)

    # ---------------- PAPER TRADING TAB ----------------
    def update_paper_view(self):
        self.paper_layout.clear_widgets()
        balance = get_balance()

        header_text = f"[b][size=18]Paper Trading Balance: ${balance:.2f}[/size][/b]\n"
        header = Label(text=header_text, markup=True, size_hint_y=None, height=50, **self.label_kwargs())
        self.paper_layout.add_widget(header)

        self.paper_layout.add_widget(Label(text="[b]Open Trades[/b]", markup=True, size_hint_y=None, height=30, **self.label_kwargs()))
        open_trades = get_open_trades()
        if not open_trades:
            self.paper_layout.add_widget(Label(text="No open trades.", size_hint_y=None, height=30, **self.label_kwargs()))
        for symbol, sig_type, entry, qty in open_trades:
            text = f"{symbol} | {sig_type} | Entry: {entry} | Qty: {qty}"
            item = Label(text=text, size_hint_y=None, height=28, **self.label_kwargs())
            self.paper_layout.add_widget(item)

        self.paper_layout.add_widget(Label(text="[b]Closed Trade History[/b]", markup=True, size_hint_y=None, height=30, **self.label_kwargs()))
        for symbol, sig_type, entry, closed, pnl in get_paper_trade_history(15):
            icon = "✅" if pnl and pnl > 0 else "❌"
            text = f"{icon} {symbol} {sig_type} | Entry: {entry} -> {closed} | PnL: ${pnl:.2f}"
            item = Label(text=text, size_hint_y=None, height=28, **self.label_kwargs())
            self.paper_layout.add_widget(item)

    # ---------------- SETTINGS TAB ----------------
    def build_settings_tab(self, settings_tab):
        scroll = ScrollView()
        layout = BoxLayout(orientation="vertical", size_hint_y=None, spacing=10, padding=15)
        layout.bind(minimum_height=layout.setter("height"))

        self.setting_inputs = {}

        def add_row(label_text, key, value):
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=45, spacing=10)
            row.add_widget(Label(text=label_text, size_hint_x=0.6, **self.label_kwargs()))
            ti = TextInput(text=str(value), size_hint_x=0.4, multiline=False)
            self.setting_inputs[key] = ti
            row.add_widget(ti)
            layout.add_widget(row)

        add_row("RSI Oversold Level", "rsi_oversold", self.settings["rsi_oversold"])
        add_row("RSI Overbought Level", "rsi_overbought", self.settings["rsi_overbought"])
        add_row("Min Score for Alert", "min_score_alert", self.settings["min_score_alert"])
        add_row("Top N Coins to Scan", "top_n_coins", self.settings["top_n_coins"])
        add_row("Account Balance ($)", "account_balance", self.settings["account_balance"])
        add_row("Risk % per Trade", "risk_percent", self.settings["risk_percent"])
        add_row("Telegram Bot Token", "telegram_bot_token", self.settings["telegram_bot_token"])
        add_row("Telegram Chat ID", "telegram_chat_id", self.settings["telegram_chat_id"])

        toggle_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=45, spacing=10)
        toggle_row.add_widget(Label(text="Enable Telegram Alerts", size_hint_x=0.6, **self.label_kwargs()))
        self.telegram_toggle = ToggleButton(text="ON" if self.settings["telegram_enabled"] else "OFF",
                                            state="down" if self.settings["telegram_enabled"] else "normal",
                                            size_hint_x=0.4)
        toggle_row.add_widget(self.telegram_toggle)
        layout.add_widget(toggle_row)

        paper_toggle_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=45, spacing=10)
        paper_toggle_row.add_widget(Label(text="Enable Paper Trading", size_hint_x=0.6, **self.label_kwargs()))
        self.paper_toggle = ToggleButton(text="ON" if self.settings["paper_trading_enabled"] else "OFF",
                                         state="down" if self.settings["paper_trading_enabled"] else "normal",
                                         size_hint_x=0.4)
        paper_toggle_row.add_widget(self.paper_toggle)
        layout.add_widget(paper_toggle_row)

        save_btn = Button(text="Save Settings", size_hint_y=None, height=50)
        save_btn.bind(on_press=lambda x: self.save_settings_from_ui())
        layout.add_widget(save_btn)

        self.settings_status = Label(text="", size_hint_y=None, height=30, **self.label_kwargs())
        layout.add_widget(self.settings_status)

        scroll.add_widget(layout)
        settings_tab.add_widget(scroll)

    def save_settings_from_ui(self):
        try:
            self.settings["rsi_oversold"] = float(self.setting_inputs["rsi_oversold"].text)
            self.settings["rsi_overbought"] = float(self.setting_inputs["rsi_overbought"].text)
            self.settings["min_score_alert"] = float(self.setting_inputs["min_score_alert"].text)
            self.settings["top_n_coins"] = int(self.setting_inputs["top_n_coins"].text)
            self.settings["account_balance"] = float(self.setting_inputs["account_balance"].text)
            self.settings["risk_percent"] = float(self.setting_inputs["risk_percent"].text)
            self.settings["telegram_bot_token"] = self.setting_inputs["telegram_bot_token"].text
            self.settings["telegram_chat_id"] = self.setting_inputs["telegram_chat_id"].text
            self.settings["telegram_enabled"] = self.telegram_toggle.state == "down"
            self.settings["paper_trading_enabled"] = self.paper_toggle.state == "down"

            save_settings(self.settings)
            self.settings_status.text = "✅ Settings saved successfully!"
        except ValueError as e:
            self.settings_status.text = f"❌ Error: Check your input values ({e})"


if __name__ == "__main__":
    CryptoScannerApp().run()
