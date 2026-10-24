"""Taiwan daily-bar selection and date notices, independent of Streamlit."""

from datetime import datetime, time, timedelta
from functools import lru_cache
import logging
import math
from zoneinfo import ZoneInfo

import pandas as pd

TAIPEI = ZoneInfo("Asia/Taipei")
MARKET_OPEN = time(9)
MARKET_CLOSE = time(13, 30)
# UI warning threshold only; Yahoo does not promise delivery at this time.
UPDATE_WARNING_TIME = time(15)
LOOKBACK_DAYS = (30, 90)
COLUMNS = ["族群", "股票", "代號", "最新股價", "漲跌幅(%)", "成交量"]
logger = logging.getLogger(__name__)


def taipei_now():
    return datetime.now(TAIPEI)


def normalize_daily_data(frame, target_date):
    """Naive daily labels are local dates; aware timestamps convert to Taipei."""
    if frame is None or frame.empty:
        return pd.DataFrame()
    frame = frame.copy()
    index = pd.DatetimeIndex(frame.index)
    if index.tz is not None:
        index = index.tz_convert(TAIPEI).tz_localize(None)
    frame.index = index.normalize()
    frame = frame.loc[~frame.index.isna()]
    frame = frame.loc[frame.index <= pd.Timestamp(target_date)]
    return frame.loc[~frame.index.duplicated(keep="last")].sort_index()


def valid_close_dates(frame, tickers):
    if frame.empty or "Close" not in frame:
        return pd.DatetimeIndex([])
    closes = frame["Close"].reindex(columns=tickers).apply(pd.to_numeric, errors="coerce")
    valid = closes.gt(0) & closes.lt(float("inf"))
    return closes.index[valid.any(axis=1)]


def select_snapshot(raw, target_date, ticker_map):
    """Use one common pair of observed dates; never silently mix stock dates."""
    frame = normalize_daily_data(raw, target_date)
    dates = valid_close_dates(frame, list(ticker_map))
    actual = dates[-1].date() if len(dates) else None
    previous = dates[-2].date() if len(dates) >= 2 else None
    metadata = {"actual_date": actual, "previous_date": previous, "excluded": []}
    rows = []
    if previous is None:
        return pd.DataFrame(columns=COLUMNS), metadata
    for ticker, info in ticker_map.items():
        try:
            c1 = float(frame["Close"].loc[pd.Timestamp(actual), ticker])
            c0 = float(frame["Close"].loc[pd.Timestamp(previous), ticker])
            volume = float(frame["Volume"].loc[pd.Timestamp(actual), ticker])
            if not all(math.isfinite(v) for v in (c1, c0, volume)):
                raise ValueError("Non-finite daily bar")
            if c1 <= 0 or c0 <= 0 or volume < 0:
                raise ValueError("Invalid daily bar")
            rows.append({
                "族群": info["group"], "股票": info["name"], "代號": ticker,
                "最新股價": round(c1, 2),
                "漲跌幅(%)": round((c1 - c0) / c0 * 100, 2),
                "成交量": int(volume),
            })
        except (KeyError, TypeError, ValueError, OverflowError):
            metadata["excluded"].append(ticker)
    return pd.DataFrame(rows, columns=COLUMNS), metadata


def download_snapshot(target_date, ticker_map, download):
    """Bounded retry for long holidays; retain Yahoo's exclusive end semantics."""
    result = pd.DataFrame(columns=COLUMNS)
    metadata = {"actual_date": None, "previous_date": None, "excluded": []}
    for days in LOOKBACK_DAYS:
        raw = download(
            list(ticker_map),
            start=(target_date - timedelta(days=days)).isoformat(),
            end=(target_date + timedelta(days=1)).isoformat(),
            interval="1d", group_by="column", auto_adjust=True, progress=False,
        )
        result, metadata = select_snapshot(raw, target_date, ticker_map)
        metadata["lookback_days"] = days
        if metadata["previous_date"] is not None:
            break
    metadata["fetched_at"] = taipei_now()
    return result, metadata


@lru_cache(maxsize=8)
def calendar_sessions(year):
    """Local XTAI schedule; not a live official emergency-closure feed."""
    try:
        import exchange_calendars as xcals

        calendar = xcals.get_calendar(
            "XTAI", start=f"{year - 1}-01-01", end=f"{year}-12-31"
        )
        return tuple(calendar.sessions.date)
    except Exception:
        logger.exception("XTAI calendar unavailable for %s", year)
        return ()


def date_notices(target_date, actual, previous, now, sessions):
    """Return (Streamlit level, message), recomputed outside the quote cache."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(TAIPEI)
    notices = []
    if not sessions:
        notices.append(("warning", "交易日曆無法使用；目前僅依實際報價回溯，無法確認休市或資料延遲。"))
        if actual is not None and actual < target_date:
            notices.append(("info", f"查詢日沒有可用資料，已回溯至 {actual:%Y-%m-%d}。"))
        if actual == now.date():
            notices.append(("warning", "當日資料可能尚未完整，不能視為已確認的收盤資料。"))
        return notices

    sessions = sorted(set(d for d in sessions if d <= target_date))
    if not sessions:
        return [("warning", "交易日曆未涵蓋查詢範圍，請依實際資料日期判讀。")]
    is_session = target_date in sessions
    today = target_date == now.date()
    expected = sessions[-1]
    if today and is_session and now.time() < MARKET_OPEN:
        expected = sessions[-2] if len(sessions) > 1 else None
        notices.append(("info", "台灣時間尚未開盤；今日行情尚未產生，顯示最近可用資料。"))
    elif today and is_session and now.time() < MARKET_CLOSE:
        notices.append(("warning", "台灣市場盤中：今日價格與成交量可能持續變動，非完整收盤資料；尚無今日資料時會回溯。"))
    elif today and is_session:
        notices.append(("info", "台灣市場已收盤；Yahoo 日線仍可能補登或修正，收盤不代表資料已完整更新。"))

    if not is_session:
        notices.append(("info", f"查詢日依 XTAI 日曆為非交易日，最近排定交易日為 {expected:%Y-%m-%d}；依實際可用資料回溯。"))
    if actual is not None and actual < target_date:
        notices.append(("info", f"日期不同：查詢 {target_date:%Y-%m-%d} → 實際採用 {actual:%Y-%m-%d}。"))
    if actual is not None and actual not in sessions:
        notices.append(("warning", "實際資料日與交易日曆不一致；保留供應商資料，請核對交易所公告。"))
    if expected is not None and (actual is None or actual < expected):
        waiting = today and is_session and expected == target_date and now.time() < UPDATE_WARNING_TIME
        notices.append(("info" if waiting else "warning",
                        f"尚無 {expected:%Y-%m-%d} 的可用資料；"
                        + ("可能尚未更新，請稍後重新整理。" if waiting else
                           "可能為供應商延遲、下載缺漏或臨時休市，請核對交易所公告並重新整理。")))
    if actual is not None and previous is not None:
        between = [d for d in sessions if previous < d < actual]
        if between:
            notices.append(("warning", f"比較期間缺少 {len(between)} 個排定交易日的有效價格；漲跌幅為 {previous:%Y-%m-%d} 至 {actual:%Y-%m-%d} 的區間變動，不是單日漲跌。"))
    return notices
