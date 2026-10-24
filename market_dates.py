"""台股日線日期判斷（以台灣時間及資料來源實際可用日期為準）。"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
# 16:00 僅是盤後資料可能較完整的提醒門檻，不是供應商保證更新時間。
DAILY_DATA_CAUTION_BEFORE = time(16, 0)


def taiwan_now():
    """避免雲端主機採用 UTC 時，日期選擇器跳到錯誤日期。"""
    return datetime.now(TAIPEI)


def taiwan_date(timestamp):
    """帶時區時間戳先轉台灣時間；無時區日線視為交易所當地日期。"""
    if isinstance(timestamp, datetime):
        if timestamp.tzinfo is not None:
            return timestamp.astimezone(TAIPEI).date()
        return timestamp.date()
    if isinstance(timestamp, date):
        return timestamp
    raise TypeError(f"無法辨識日線日期格式: {type(timestamp)!r}")


def last_two_sessions(closes, query_date):
    """從 Yahoo 實際回傳的有效收盤價列，找不晚於查詢日的兩個資料日。"""
    nonempty = closes.dropna(how="all")
    eligible = sorted(ts for ts in nonempty.index if taiwan_date(ts) <= query_date)
    if len(eligible) < 2:
        return None, None
    return eligible[-1], eligible[-2]


def data_date_notice(query_date, actual_date, now):
    """回傳 (Streamlit 提示等級, 訊息)，沒有異常時回傳 None。"""
    local_now = now.astimezone(TAIPEI) if now.tzinfo else now.replace(tzinfo=TAIPEI)
    today = local_now.date()

    if actual_date is None:
        return ("warning", "尚未取得足夠的歷史日線資料，無法判定實際交易日。")
    if actual_date < query_date:
        actual = actual_date.isoformat()
        if query_date.weekday() >= 5:
            previous_friday = query_date - timedelta(days=query_date.weekday() - 4)
            if actual_date < previous_friday:
                return ("warning", f"查詢日為週末，已回溯至 {actual}；該日期早於一般週五交易日，可能遇到連假休市或資料來源延遲。")
            return ("info", f"查詢日為週末非交易日，已自動回溯至 {actual} 的可用日線資料。")
        if query_date == today and local_now.time() < DAILY_DATA_CAUTION_BEFORE:
            return ("warning", f"今日日線可能尚未更新或定稿，目前顯示最近可用交易日 {actual}；請稍後再查看。")
        if query_date == today:
            return ("warning", f"今日尚未取得對應日線（可能休市或資料來源延遲），目前顯示 {actual} 的資料。")
        return ("warning", f"查詢日沒有可用日線（可能休市或資料來源缺漏），已回溯至 {actual}；不代表查詢日當天有交易。")
    if actual_date == today and query_date == today and local_now.time() < DAILY_DATA_CAUTION_BEFORE:
        return ("warning", "今日的 Yahoo Finance 日線可能是盤中或尚未定稿資料，漲跌幅及成交量仍可能變動（台灣時間 16:00 前請特別留意）。")
    return None
