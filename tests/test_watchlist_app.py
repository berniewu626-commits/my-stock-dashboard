import json
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from test_watchlist import bars, SYMBOL, DAY

ROOT = Path(__file__).resolve().parents[1]
PANEL = '''from datetime import date
from watchlist_ui import render_watchlist
render_watchlist(date(2026, 10, 24))
'''


def button(app, label):
    return next(b for b in app.button if b.label == label)


def add(app, text):
    app.text_area[0].input(text)
    button(app, "加入／匯入自選股").click().run()
    return app


class WatchlistAppTests(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()
        self.mock = patch("yfinance.download", return_value=bars()).start()
        self.addCleanup(patch.stopall)

    def panel(self):
        return AppTest.from_string(PANEL).run()

    def test_add_dedupe_delete_last_and_session_isolation(self):
        app = self.panel()
        self.assertEqual(app.session_state.watchlist_symbols, [])
        self.assertFalse(self.mock.called)
        add(app, "6715.tw, 6715")
        self.assertEqual(app.session_state.watchlist_symbols, [SYMBOL])
        self.assertFalse(app.exception)
        quote = app.dataframe[0].value.iloc[0]
        self.assertEqual(quote["最新股價"], 105)
        self.assertEqual(quote["實際資料交易日"], date(2026, 10, 23))
        chart = json.loads(app.get("plotly_chart")[0].proto.spec)
        self.assertEqual(chart["data"][0]["type"], "candlestick")
        self.assertEqual(len(chart["data"][0]["x"]), 2)
        fresh = self.panel()
        self.assertEqual(fresh.session_state.watchlist_symbols, [])
        app.multiselect[0].select(SYMBOL)
        button(app, "刪除所選股票").click().run()
        self.assertEqual(app.session_state.watchlist_symbols, [])
        self.assertFalse(app.dataframe)
        self.assertFalse(app.exception)

    def test_invalid_input_leaves_list_unchanged(self):
        app = add(self.panel(), SYMBOL)
        add(app, "2330.TW, BAD")
        self.assertEqual(app.session_state.watchlist_symbols, [SYMBOL])
        self.assertTrue(app.error)

    def test_cache_refresh_and_query_date(self):
        app = add(self.panel(), SYMBOL)
        count = self.mock.call_count
        app.run()
        self.assertEqual(self.mock.call_count, count)
        button(app, "更新自選股行情").click().run()
        self.assertEqual(self.mock.call_count, count + 1)
        from watchlist_ui import get_watch_history
        get_watch_history(SYMBOL, date(2026, 10, 22))
        self.assertEqual(self.mock.call_count, count + 2)

    def test_failure_and_empty_do_not_hide_other_symbols(self):
        def response(symbol, **kwargs):
            if symbol == "9999.TW":
                raise RuntimeError("provider failure")
            return pd.DataFrame() if symbol == "8888.TW" else bars()
        self.mock.side_effect = response
        app = add(self.panel(), "9999.TW,8888.TW,6715.TW")
        self.assertFalse(app.exception)
        self.assertEqual(app.dataframe[0].value["代號"].tolist(), [SYMBOL])
        self.assertGreaterEqual(len(app.warning), 2)

    def test_all_empty_and_missing_ohlc(self):
        self.mock.return_value = pd.DataFrame()
        app = add(self.panel(), SYMBOL)
        self.assertFalse(app.exception)
        self.assertFalse(app.dataframe)
        self.mock.return_value = bars().iloc[[0]][["Close"]]
        button(app, "更新自選股行情").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe[0].value), 1)
        self.assertFalse(app.get("plotly_chart"))

    def test_delete_selected_chart_and_import_export(self):
        app = add(self.panel(), "6715.TW,2330.TW")
        self.assertEqual(len(app.get("download_button")), 1)
        app.multiselect[0].select(SYMBOL)
        button(app, "刪除所選股票").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="watchlist_chart_symbol").value, "2330.TW")

    def test_full_app_preserves_28_groups_and_date_query(self):
        def response(symbols, **kwargs):
            if isinstance(symbols, list):
                return pd.concat({s: bars() for s in symbols}, axis=1).swaplevel(axis=1)
            # Existing sector chart expects MultiIndex, like yfinance default.
            return pd.concat({symbols: bars() * (1 + int(symbols.split(".")[0]) / 10000)}, axis=1).swaplevel(axis=1)
        self.mock.side_effect = response
        patch("market_dates.taiwan_now", return_value=datetime(2026, 10, 24, 18, tzinfo=ZoneInfo("Asia/Taipei"))).start()
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        self.assertFalse(app.exception)
        group = next(s for s in app.selectbox if "深入研究族群" in s.label)
        self.assertEqual(len(group.options), 28)
        group.select("金融保險").run()
        add(app, SYMBOL)
        self.assertFalse(app.exception)
        self.assertIn(SYMBOL, app.dataframe[0].value["代號"].tolist())
        self.assertNotIn(SYMBOL, app.dataframe[-1].value["代號"].tolist())
        self.assertEqual(next(s for s in app.selectbox if "深入研究族群" in s.label).value, "金融保險")
        app.date_input[0].set_value(date(2026, 10, 22)).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.dataframe[0].value.iloc[0]["實際資料交易日"], date(2026, 10, 22))
