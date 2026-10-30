import unittest
from datetime import date
from unittest.mock import Mock

import numpy as np
import pandas as pd

from watchlist import (add_symbols, parse_symbols, normalize_history,
                       summarize_history, candle_history, download_history)

# Public market identifier used only as a synthetic validation fixture.
SYMBOL = "6715.TW"
DAY = date(2026, 10, 24)


def bars():
    return pd.DataFrame({"Open": [99., 101.], "High": [102., 106.],
                         "Low": [98., 100.], "Close": [100., 105.],
                         "Volume": [1000., 2000.]},
                        index=pd.to_datetime(["2026-10-22", "2026-10-23"]))


class WatchlistTests(unittest.TestCase):
    def test_normalization_suffixes_and_leading_zeros(self):
        self.assertEqual(parse_symbols(" 6715，0050.tw\n5347.TWO;00632R "),
                         [SYMBOL, "0050.TW", "5347.TWO", "00632R.TW"])
        self.assertEqual(parse_symbols("5347", "TWO"), ["5347.TWO"])

    def test_duplicates_and_empty(self):
        self.assertEqual(add_symbols([SYMBOL], "6715,6715.tw"), [SYMBOL])
        self.assertEqual(parse_symbols("  "), [])

    def test_invalid_input_is_atomic(self):
        current = [SYMBOL]
        for text in ("2330;AAPL", "2330.HK", "../1234", "12.TW", "1234567.TW"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                add_symbols(current, text)
        self.assertEqual(current, [SYMBOL])

    def test_limit_and_export_import_roundtrip(self):
        current = [f"{1000+i}.TW" for i in range(30)]
        self.assertEqual(add_symbols(current, current[0]), current)
        with self.assertRaises(ValueError):
            add_symbols(current, SYMBOL)
        self.assertEqual(parse_symbols("\n".join(current)), current)

    def test_weekend_quote_and_candle_same_snapshot(self):
        frame = normalize_history(bars(), SYMBOL, DAY)
        quote = summarize_history(frame, SYMBOL)
        self.assertEqual(quote["實際資料交易日"], date(2026, 10, 23))
        self.assertEqual(quote["比較基準日"], date(2026, 10, 22))
        self.assertEqual(quote["最新股價"], 105)
        self.assertEqual(quote["漲跌幅(%)"], 5)
        self.assertEqual(quote["成交量(股)"], 2000)
        self.assertEqual(candle_history(frame).index[-1].date(), quote["實際資料交易日"])

    def test_multiindex_both_orientations_and_wrong_symbol(self):
        raw = pd.concat({SYMBOL: bars(), "2330.TW": bars() * 2}, axis=1)
        for data in (raw, raw.swaplevel(axis=1)):
            with self.subTest(columns=data.columns):
                self.assertEqual(summarize_history(normalize_history(data, SYMBOL, DAY), SYMBOL)["最新股價"], 105)
        self.assertTrue(normalize_history(raw, "9999.TW", DAY).empty)

    def test_sort_deduplicate_and_future_filter(self):
        raw = pd.concat([bars().iloc[::-1], bars().iloc[[0]] * 2])
        raw.loc[pd.Timestamp("2026-10-26")] = [200, 210, 190, 205, 1000]
        frame = normalize_history(raw, SYMBOL, DAY)
        self.assertEqual(frame.Close.tolist(), [200, 105])

    def test_utc_to_taiwan_date(self):
        raw = bars().iloc[[0]]
        raw.index = pd.to_datetime(["2026-10-22 16:00Z"])
        frame = normalize_history(raw, SYMBOL, DAY)
        self.assertEqual(frame.index[0].date(), date(2026, 10, 23))

    def test_invalid_close_volume_and_single_record(self):
        for bad in (0, -1, np.nan, np.inf):
            raw = bars()
            raw.loc[raw.index[0], "Close"] = bad
            raw.loc[raw.index[-1], "Volume"] = -1
            quote = summarize_history(normalize_history(raw, SYMBOL, DAY), SYMBOL)
            self.assertEqual(quote["最新股價"], 105)
            self.assertIsNone(quote["漲跌幅(%)"])
            self.assertIsNone(quote["比較基準日"])
            self.assertIsNone(quote["成交量(股)"])
        raw.loc[raw.index[-1], "Volume"] = 0
        self.assertEqual(summarize_history(normalize_history(raw, SYMBOL, DAY), SYMBOL)["成交量(股)"], 0)

    def test_missing_or_inconsistent_ohlc_preserves_quote(self):
        for field, value in (("Open", np.nan), ("High", 1), ("Low", 200)):
            raw = bars()
            raw.loc[raw.index[-1], field] = value
            frame = normalize_history(raw, SYMBOL, DAY)
            self.assertEqual(summarize_history(frame, SYMBOL)["最新股價"], 105)
            self.assertEqual(len(candle_history(frame)), 1)

    def test_empty_and_missing_columns(self):
        for raw in (pd.DataFrame(), bars().drop(columns="Close")):
            self.assertIsNone(summarize_history(normalize_history(raw, SYMBOL, DAY), SYMBOL))
        frame = normalize_history(bars()[["Close"]], SYMBOL, DAY)
        self.assertIsNone(summarize_history(frame, SYMBOL)["成交量(股)"])
        self.assertTrue(candle_history(frame).empty)

    def test_symbols_have_independent_dates(self):
        newest = summarize_history(normalize_history(bars(), SYMBOL, DAY), SYMBOL)
        older = summarize_history(normalize_history(bars().iloc[[0]], "2330.TW", DAY), "2330.TW")
        self.assertNotEqual(newest["實際資料交易日"], older["實際資料交易日"])

    def test_downloader_bounds_and_price_policy(self):
        downloader = Mock(return_value=bars())
        frame = download_history(SYMBOL, DAY, downloader)
        self.assertEqual(len(frame), 2)
        self.assertEqual(downloader.call_args.args, (SYMBOL,))
        options = downloader.call_args.kwargs
        self.assertEqual(options["end"], "2026-10-25")
        self.assertFalse(options["auto_adjust"])
        self.assertEqual(options["timeout"], 15)
