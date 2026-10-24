from datetime import date, datetime, timezone
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from trading_dates import (
    TAIPEI, calendar_sessions, date_notices, download_snapshot,
    normalize_daily_data, select_snapshot, taipei_now,
)

TICKERS = {"A.TW": {"name": "A", "group": "甲"}, "B.TWO": {"name": "B", "group": "乙"}}


def bars(dates, prices=None, volumes=None, tickers=None):
    tickers = list(tickers or TICKERS)
    prices = prices if prices is not None else [[100 + i] * len(tickers) for i in range(len(dates))]
    volumes = volumes if volumes is not None else [[1000] * len(tickers) for _ in dates]
    fields = {field: pd.DataFrame(prices, index=pd.to_datetime(dates), columns=tickers)
              for field in ("Open", "High", "Low", "Close")}
    fields["Volume"] = pd.DataFrame(volumes, index=pd.to_datetime(dates), columns=tickers)
    return pd.concat(fields, axis=1)


class SnapshotTests(unittest.TestCase):
    def test_taipei_midnight_on_utc_host(self):
        with patch("trading_dates.datetime") as clock:
            clock.now.return_value = datetime(2026, 10, 23, 16, 5, tzinfo=timezone.utc).astimezone(TAIPEI)
            self.assertEqual(taipei_now().date(), date(2026, 10, 24))
            clock.now.assert_called_once_with(TAIPEI)

    def test_weekend_uses_friday_and_thursday(self):
        frame, meta = select_snapshot(bars(["2026-10-22", "2026-10-23"]), date(2026, 10, 24), TICKERS)
        self.assertEqual(meta["actual_date"], date(2026, 10, 23))
        self.assertEqual(meta["previous_date"], date(2026, 10, 22))
        self.assertEqual(frame.iloc[0]["漲跌幅(%)"], 1.0)

    def test_all_nan_and_future_rows_are_not_data_days(self):
        raw = bars(["2026-10-22", "2026-10-23", "2026-10-24", "2026-10-26"],
                   [[100, 100], [102, 103], [None, None], [110, 110]])
        frame, meta = select_snapshot(raw, date(2026, 10, 24), TICKERS)
        self.assertEqual(meta["actual_date"], date(2026, 10, 23))
        self.assertEqual(frame["漲跌幅(%)"].tolist(), [2, 3])

    def test_timezone_sorting_duplicates(self):
        raw = bars(["2026-10-22T16:00:00Z", "2026-10-21T16:00:00Z", "2026-10-22T16:00:00Z"])
        result = normalize_daily_data(raw, date(2026, 10, 23))
        self.assertEqual(list(result.index.date), [date(2026, 10, 22), date(2026, 10, 23)])
        self.assertEqual(result.iloc[-1][("Close", "A.TW")], 102)

    def test_partial_data_is_excluded_not_backfilled(self):
        frame, meta = select_snapshot(bars(["2026-10-21", "2026-10-22", "2026-10-23"],
                                          [[100, 100], [101, 101], [102, None]]), date(2026, 10, 23), TICKERS)
        self.assertEqual(frame["代號"].tolist(), ["A.TW"])
        self.assertEqual(meta["excluded"], ["B.TWO"])

    def test_invalid_price_and_volume(self):
        for invalid in [None, float("inf"), -1]:
            with self.subTest(volume=invalid):
                frame, meta = select_snapshot(bars(["2026-10-22", "2026-10-23"],
                                                  volumes=[[10, 10], [invalid, 0]]), date(2026, 10, 23), TICKERS)
                self.assertEqual(frame["代號"].tolist(), ["B.TWO"])
                self.assertIn("A.TW", meta["excluded"])
        frame, meta = select_snapshot(bars(["2026-10-22", "2026-10-23"], [[0, 100], [101, 101]]), date(2026, 10, 23), TICKERS)
        self.assertEqual(frame["代號"].tolist(), ["B.TWO"])

    def test_empty_and_one_day(self):
        for raw in [None, pd.DataFrame(), bars(["2026-10-23"])]:
            frame, meta = select_snapshot(raw, date(2026, 10, 23), TICKERS)
            self.assertTrue(frame.empty)
            self.assertIsNone(meta["previous_date"])

    def test_long_holiday_and_exclusive_end(self):
        download = Mock(return_value=bars(["2026-02-10", "2026-02-11"]))
        frame, meta = download_snapshot(date(2026, 2, 22), TICKERS, download)
        self.assertEqual(meta["actual_date"], date(2026, 2, 11))
        self.assertEqual(download.call_args.kwargs["end"], "2026-02-23")
        self.assertEqual(download.call_args.kwargs["start"], "2026-01-23")
        self.assertEqual(download.call_count, 1)

    def test_bounded_expansion_and_download_error(self):
        download = Mock(side_effect=[bars(["2026-10-23"]), bars(["2026-09-01", "2026-10-23"])])
        _, meta = download_snapshot(date(2026, 10, 24), TICKERS, download)
        self.assertEqual(meta["lookback_days"], 90)
        self.assertEqual(download.call_count, 2)
        with self.assertRaises(RuntimeError):
            download_snapshot(date(2026, 10, 24), TICKERS, Mock(side_effect=RuntimeError("offline")))


class NoticeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sessions = calendar_sessions(2026)

    def notices(self, target, actual, previous, hour=16, minute=0):
        now = datetime.combine(target, datetime.min.time(), tzinfo=TAIPEI).replace(hour=hour, minute=minute)
        return date_notices(target, actual, previous, now, self.sessions)

    def test_calendar_matches_twse_2026_closures(self):
        # https://www.twse.com.tw/holidaySchedule/holidaySchedule?response=html
        self.assertTrue(self.sessions)
        for holiday in [date(2026, 1, 1), date(2026, 2, 12), date(2026, 2, 13),
                        date(2026, 2, 20), date(2026, 9, 28), date(2026, 10, 26)]:
            self.assertNotIn(holiday, self.sessions)
        self.assertIn(date(2026, 2, 11), self.sessions)
        self.assertIn(date(2026, 2, 23), self.sessions)

    def test_weekend_and_holiday_are_not_delays(self):
        for target, actual, previous in [(date(2026, 10, 24), date(2026, 10, 23), date(2026, 10, 22)),
                                         (date(2026, 2, 22), date(2026, 2, 11), date(2026, 2, 10))]:
            notices = self.notices(target, actual, previous)
            self.assertTrue(any("非交易日" in text for _, text in notices))
            self.assertFalse(any(level == "warning" for level, _ in notices))

    def test_premarket_not_delayed_but_older_data_is_flagged(self):
        notices = self.notices(date(2026, 10, 23), date(2026, 10, 22), date(2026, 10, 21), hour=8)
        self.assertTrue(any("尚未開盤" in text for _, text in notices))
        self.assertFalse(any("尚無" in text for _, text in notices))
        notices = self.notices(date(2026, 10, 23), date(2026, 10, 21), date(2026, 10, 20), hour=8)
        self.assertTrue(any("尚無 2026-10-22" in text for _, text in notices))

    def test_intraday_data_is_explicitly_provisional(self):
        for actual in [date(2026, 10, 22), date(2026, 10, 23)]:
            notices = self.notices(date(2026, 10, 23), actual, date(2026, 10, 21), hour=10)
            self.assertTrue(any("非完整收盤資料" in text for _, text in notices))

    def test_after_close_grace_and_delayed(self):
        for hour, expected_level in [(14, "info"), (15, "warning"), (18, "warning")]:
            notices = self.notices(date(2026, 10, 23), date(2026, 10, 22), date(2026, 10, 21), hour=hour)
            level, _ = next(n for n in notices if "尚無" in n[1])
            self.assertEqual(level, expected_level)

    def test_stale_weekend_and_missing_comparison_session(self):
        notices = self.notices(date(2026, 10, 24), date(2026, 10, 22), date(2026, 10, 20))
        self.assertTrue(any(level == "warning" and "尚無 2026-10-23" in text for level, text in notices))
        self.assertTrue(any("不是單日漲跌" in text for _, text in notices))

    def test_historical_missing_data_and_empty_data(self):
        now = datetime(2026, 10, 24, 8, tzinfo=TAIPEI)
        for actual in [date(2026, 10, 21), None]:
            notices = date_notices(date(2026, 10, 22), actual, None, now, self.sessions)
            self.assertTrue(any(level == "warning" and "尚無" in text for level, text in notices))

    def test_calendar_unavailable_does_not_invent_holiday(self):
        notices = date_notices(date(2026, 10, 24), date(2026, 10, 23), date(2026, 10, 22),
                               datetime(2026, 10, 24, tzinfo=TAIPEI), ())
        self.assertTrue(any("無法確認休市或資料延遲" in text for _, text in notices))
        self.assertFalse(any("為非交易日" in text for _, text in notices))
        with patch("exchange_calendars.get_calendar", side_effect=RuntimeError("unavailable")):
            with self.assertLogs("trading_dates", level="ERROR"):
                self.assertEqual(calendar_sessions.__wrapped__(2026), ())

    def test_utc_now_is_converted_and_naive_rejected(self):
        notices = date_notices(date(2026, 10, 23), date(2026, 10, 22), None,
                               datetime(2026, 10, 23, 0, tzinfo=timezone.utc), self.sessions)
        self.assertTrue(any("尚未開盤" in text for _, text in notices))
        with self.assertRaises(ValueError):
            date_notices(date(2026, 10, 23), None, None, datetime(2026, 10, 23), self.sessions)


if __name__ == "__main__":
    unittest.main()
