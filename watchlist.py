"""User watchlists and per-symbol quotes; no default holdings or shared storage."""
import re
from datetime import timedelta

import numpy as np
import pandas as pd

from market_dates import taiwan_date

MAX_SYMBOLS = 30
SYMBOL = re.compile(r"[0-9]{4,6}[A-Z]{0,2}\.(?:TW|TWO)\Z")
FIELDS = ["Open", "High", "Low", "Close", "Volume"]


def parse_symbols(text, default_market="TW"):
    """Normalize pasted lists atomically; keep suffixes and leading zeros."""
    if default_market not in ("TW", "TWO"):
        raise ValueError("市場必須是 TW 或 TWO。")
    tokens = re.split(r"[\s,，、;；]+", text.strip().upper())
    result = []
    for token in filter(None, tokens):
        symbol = token if "." in token else f"{token}.{default_market}"
        if not SYMBOL.fullmatch(symbol):
            raise ValueError(f"代號格式不正確：{token}；請使用台股代號與 .TW／.TWO。")
        if symbol not in result:
            result.append(symbol)
    return result


def add_symbols(current, text, default_market="TW"):
    result = list(dict.fromkeys([*current, *parse_symbols(text, default_market)]))
    if len(result) > MAX_SYMBOLS:
        raise ValueError(f"最多可觀察 {MAX_SYMBOLS} 檔股票。")
    return result


def normalize_history(raw, symbol, query_date):
    """Accept flat or either yfinance MultiIndex layout; never mix symbols."""
    if raw is None or raw.empty:
        return pd.DataFrame(columns=FIELDS)
    frame = raw.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        for level in range(frame.columns.nlevels):
            if symbol in frame.columns.get_level_values(level):
                frame = frame.xs(symbol, axis=1, level=level)
                break
        else:
            return pd.DataFrame(columns=FIELDS)
    if isinstance(frame.columns, pd.MultiIndex) or "Close" not in frame:
        return pd.DataFrame(columns=FIELDS)
    frame = frame.reindex(columns=FIELDS).apply(pd.to_numeric, errors="coerce")
    frame.index = pd.DatetimeIndex([taiwan_date(pd.Timestamp(ts)) for ts in frame.index])
    frame = frame.sort_index(kind="stable")
    frame = frame.loc[~frame.index.duplicated(keep="last")]
    frame = frame.loc[frame.index.date <= query_date]
    frame = frame.replace([np.inf, -np.inf], np.nan)
    frame = frame.loc[frame.Close.notna() & (frame.Close > 0)]
    frame.loc[frame.Volume < 0, "Volume"] = np.nan
    return frame


def summarize_history(frame, symbol):
    if frame.empty:
        return None
    latest = frame.iloc[-1]
    previous = frame.iloc[-2] if len(frame) > 1 else None
    return {
        "代號": symbol,
        "實際資料交易日": frame.index[-1].date(),
        "比較基準日": frame.index[-2].date() if previous is not None else None,
        "最新股價": round(float(latest.Close), 2),
        "漲跌幅(%)": round((float(latest.Close) / float(previous.Close) - 1) * 100, 2) if previous is not None else None,
        "成交量(股)": int(latest.Volume) if pd.notna(latest.Volume) else None,
    }


def candle_history(frame):
    """A missing candle must not invalidate a usable closing quote."""
    valid = frame.dropna(subset=["Open", "High", "Low", "Close"])
    valid = valid.loc[(valid[["Open", "High", "Low", "Close"]] > 0).all(axis=1)]
    return valid.loc[(valid.High >= valid[["Open", "Low", "Close"]].max(axis=1)) &
                     (valid.Low <= valid[["Open", "High", "Close"]].min(axis=1))]


def download_history(symbol, query_date, downloader):
    raw = downloader(symbol, start=(query_date - timedelta(days=180)).isoformat(),
                     end=(query_date + timedelta(days=1)).isoformat(),
                     auto_adjust=False, progress=False, threads=False, timeout=15)
    return normalize_history(raw, symbol, query_date)
