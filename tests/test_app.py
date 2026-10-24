"""Offline UI regression tests: no Yahoo requests or account credentials."""

from datetime import date, datetime
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from trading_dates import TAIPEI
from test_trading_dates import bars

APP = str(Path(__file__).resolve().parents[1] / "app.py")


class AppTests(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()
        self.clock = patch("trading_dates.taipei_now", return_value=datetime(2026, 10, 24, 19, tzinfo=TAIPEI))
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.calls = []

    def download(self, tickers, **kwargs):
        self.calls.append((tickers, kwargs))
        names = [tickers] if isinstance(tickers, str) else tickers
        return bars(["2026-10-22", "2026-10-23"], tickers=names)

    def test_existing_ui_date_labels_chart_alignment_and_refresh(self):
        with patch("yfinance.download", side_effect=self.download):
            app = AppTest.from_file(APP).run(timeout=20)
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.sidebar.date_input[0].value, date(2026, 10, 24))
            self.assertEqual(app.sidebar.date_input[0].max, date(2026, 10, 24))
            captions = "\n".join(c.value for c in app.caption)
            self.assertIn("查詢日期：2026-10-24", captions)
            self.assertIn("實際資料日期：2026-10-23", captions)
            self.assertIn("比較基準日：2026-10-22", captions)
            self.assertEqual(len(app.dataframe), 2)
            self.assertEqual(len(app.selectbox), 1)
            self.assertGreater(len(app.get("plotly_chart")), 1)
            for tickers, kwargs in self.calls:
                if isinstance(tickers, str):
                    self.assertEqual(kwargs["end"], "2026-10-24")
            app.selectbox[0].select("IC設計").run(timeout=20)
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(sum(isinstance(t, list) for t, _ in self.calls), 1)
            app.sidebar.button[0].click().run(timeout=20)
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(sum(isinstance(t, list) for t, _ in self.calls), 2)

    def test_empty_data_keeps_dates_and_actionable_message(self):
        with patch("yfinance.download", return_value=pd.DataFrame()):
            app = AppTest.from_file(APP).run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("無可用資料" in c.value for c in app.caption))
        self.assertIn("回查 90 天", app.error[0].value)

    def test_download_failure_is_not_called_a_holiday(self):
        with patch("yfinance.download", side_effect=RuntimeError("offline")):
            app = AppTest.from_file(APP).run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertIn("下載失敗", app.error[0].value)
        self.assertEqual(len(app.dataframe), 0)

    def test_chart_failure_does_not_break_dashboard(self):
        def download(tickers, **kwargs):
            if isinstance(tickers, str):
                raise RuntimeError("chart unavailable")
            return self.download(tickers, **kwargs)

        with patch("yfinance.download", side_effect=download):
            app = AppTest.from_file(APP).run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.dataframe), 2)
        self.assertTrue(any("K 線暫無" in c.value for c in app.caption))

    def test_one_day_stale_chart_remains_a_series_and_warns(self):
        def download(tickers, **kwargs):
            if isinstance(tickers, str):
                return bars(["2026-10-22"], tickers=[tickers])
            return self.download(tickers, **kwargs)

        with patch("yfinance.download", side_effect=download):
            app = AppTest.from_file(APP).run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("K 線尚未更新" in w.value for w in app.warning))


if __name__ == "__main__":
    unittest.main()
