"""執行：python -m unittest discover -s tests -v"""

import unittest
from datetime import date, datetime, timezone

import pandas as pd

from market_dates import data_date_notice, last_two_sessions, taiwan_date


class MarketDateTests(unittest.TestCase):
    def test_taiwan_time_rollover(self):
        self.assertEqual(taiwan_date(datetime(2026, 10, 23, 17, 0, tzinfo=timezone.utc)), date(2026, 10, 24))

    def test_naive_yahoo_daily_index_means_local_exchange_date(self):
        self.assertEqual(taiwan_date(pd.Timestamp("2026-10-23")), date(2026, 10, 23))

    def test_weekend_uses_latest_two_valid_days(self):
        frame = pd.DataFrame({"2330.TW": [100, 101, 102]}, index=pd.to_datetime(["2026-10-21", "2026-10-22", "2026-10-23"]))
        current, previous = last_two_sessions(frame, date(2026, 10, 24))
        self.assertEqual(taiwan_date(current), date(2026, 10, 23))
        self.assertEqual(taiwan_date(previous), date(2026, 10, 22))
        level, notice = data_date_notice(date(2026, 10, 24), taiwan_date(current), datetime(2026, 10, 24, 11, 0, tzinfo=timezone.utc))
        self.assertEqual(level, "info")
        self.assertIn("週末", notice)

    def test_weekend_data_older_than_friday_warns(self):
        level, notice = data_date_notice(date(2026, 10, 24), date(2026, 10, 22), datetime(2026, 10, 24, 11, 0, tzinfo=timezone.utc))
        self.assertEqual(level, "warning")
        self.assertIn("可能遇到連假", notice)

    def test_long_holiday_backfill(self):
        frame = pd.DataFrame({"2330.TW": [100, 105]}, index=pd.to_datetime(["2026-02-10", "2026-02-11"]))
        latest, previous = last_two_sessions(frame, date(2026, 2, 21))
        self.assertEqual(taiwan_date(latest), date(2026, 2, 11))
        self.assertEqual(taiwan_date(previous), date(2026, 2, 10))

    def test_all_nan_row_does_not_count_as_session(self):
        frame = pd.DataFrame({"a": [10.0, 11.0, float("nan")], "b": [12.0, 13.0, float("nan")]}, index=pd.to_datetime(["2026-10-21", "2026-10-22", "2026-10-23"]))
        latest, _ = last_two_sessions(frame, date(2026, 10, 23))
        self.assertEqual(taiwan_date(latest), date(2026, 10, 22))

    def test_before_eod_with_current_day_data_warns(self):
        level, notice = data_date_notice(date(2026, 10, 23), date(2026, 10, 23), datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc))
        self.assertEqual(level, "warning")
        self.assertIn("盤中", notice)

    def test_before_eod_missing_data_warns(self):
        level, notice = data_date_notice(date(2026, 10, 23), date(2026, 10, 22), datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc))
        self.assertEqual(level, "warning")
        self.assertIn("尚未更新", notice)

    def test_after_eod_missing_data_still_warns(self):
        level, notice = data_date_notice(date(2026, 10, 23), date(2026, 10, 22), datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc))
        self.assertEqual(level, "warning")
        self.assertIn("延遲", notice)

    def test_historical_weekday_gap_has_cautious_language(self):
        level, notice = data_date_notice(date(2026, 10, 22), date(2026, 10, 21), datetime(2026, 10, 24, 5, 0, tzinfo=timezone.utc))
        self.assertEqual(level, "warning")
        self.assertIn("可能休市", notice)

    def test_matching_historical_date_no_notice(self):
        self.assertIsNone(data_date_notice(date(2026, 10, 22), date(2026, 10, 22), datetime(2026, 10, 24, 5, 0, tzinfo=timezone.utc)))

    def test_insufficient_trading_days(self):
        frame = pd.DataFrame({"a": [100]}, index=pd.to_datetime(["2026-10-23"]))
        self.assertEqual(last_two_sessions(frame, date(2026, 10, 24)), (None, None))


if __name__ == "__main__":
    unittest.main()
