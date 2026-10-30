"""Isolated Streamlit watchlist panel; lists live only in the current session."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

from market_dates import data_date_notice, taiwan_now
from watchlist import add_symbols, candle_history, download_history, summarize_history


@st.cache_data(ttl=300, max_entries=256, show_spinner=False)
def get_watch_history(symbol, query_date):
    return download_history(symbol, query_date, yf.download)


def render_watchlist(query_date):
    st.subheader("⭐ 自選股觀察區")
    st.caption("清單僅保留於目前連線；重新整理或重啟可能清空。可下載備份，下次貼上匯入。")
    if "watchlist_symbols" not in st.session_state:
        st.session_state.watchlist_symbols = []
    with st.form("watchlist_add", clear_on_submit=True):
        entered = st.text_area("輸入股票代號／貼上清單", placeholder="例如：2330.TW, 5347.TWO, 0050.TW")
        market = st.selectbox("未填後綴時使用市場", ["TW", "TWO"],
                              format_func=lambda s: "上市 .TW" if s == "TW" else "上櫃 .TWO")
        submitted = st.form_submit_button("加入／匯入自選股")
    if submitted:
        try:
            before = st.session_state.watchlist_symbols
            after = add_symbols(before, entered, market)
            st.session_state.watchlist_symbols = after
            st.success(f"新增 {len(after) - len(before)} 檔；重複代號已略過。")
        except ValueError as exc:
            st.error(str(exc))

    symbols = st.session_state.watchlist_symbols
    if not symbols:
        st.info("尚無自選股。輸入代號即可開始觀察，最多 30 檔。")
        return
    with st.form("watchlist_remove"):
        removed = st.multiselect("選擇要刪除的股票", symbols)
        if st.form_submit_button("刪除所選股票"):
            st.session_state.watchlist_symbols = [s for s in symbols if s not in removed]
            st.rerun()
    st.download_button("下載自選清單", "\n".join(symbols) + "\n",
                       file_name="watchlist.txt", mime="text/plain", key="watchlist_export")
    if st.button("更新自選股行情", key="watchlist_refresh"):
        for symbol in symbols:
            get_watch_history.clear(symbol, query_date)
    st.caption(f"查詢日期：{query_date:%Y-%m-%d}｜顯示截至查詢日的最近可用日線，行情快取 5 分鐘。"
               "漲跌幅以各股前一筆有效收盤價計算；跨缺漏日期時為區間報酬，請對照比較基準日。"
               "股價與 K 線採未還原價格，除權息可能影響漲跌幅；成交量單位為股。")
    rows, histories = [], {}
    with st.spinner("正在取得自選股行情…"):
        for symbol in symbols:
            try:
                history = get_watch_history(symbol, query_date)
                quote = summarize_history(history, symbol)
                if quote is None:
                    st.warning(f"{symbol}：近 180 天無可用資料；請確認代號、上市／上櫃後綴，或稍後更新重試。")
                    continue
                rows.append(quote)
                histories[symbol] = history
            except Exception:
                st.warning(f"{symbol}：行情取得失敗，請稍後更新重試。")
    if not rows:
        return
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                 column_config={"最新股價": st.column_config.NumberColumn(format="%.2f"),
                                "漲跌幅(%)": st.column_config.NumberColumn(format="%.2f"),
                                "成交量(股)": st.column_config.NumberColumn(format="%d")})
    selected = st.selectbox("自選股 K 線", list(histories), key="watchlist_chart_symbol")
    quote = next(row for row in rows if row["代號"] == selected)
    notice = data_date_notice(query_date, quote["實際資料交易日"], taiwan_now())
    if notice:
        getattr(st, notice[0])(notice[1])
    if quote["比較基準日"] is None:
        st.info("僅一筆有效收盤價，無法計算漲跌幅。")
    candles = candle_history(histories[selected])
    if candles.empty:
        st.warning("開高低收資料不足，暫時無法繪製 K 線。")
    else:
        last_candle = candles.index[-1].date()
        st.caption(f"{selected}｜K 線截至：{last_candle:%Y-%m-%d}｜有效 K 線：{len(candles)} 筆")
        if len(candles) != len(histories[selected]):
            st.warning("部分日線開高低收不完整，已略過；K 線可能與最新報價日期不同。")
        fig = go.Figure(go.Candlestick(x=candles.index, open=candles.Open,
                         high=candles.High, low=candles.Low, close=candles.Close,
                         increasing_line_color="#ef5350", decreasing_line_color="#26a69a"))
        fig.update_layout(height=380, template="plotly_dark", xaxis_rangeslider_visible=False,
                          margin=dict(l=0, r=0, t=10, b=0), yaxis_title="股價（元）")
        st.plotly_chart(fig, use_container_width=True, key="watchlist_candlestick")
    st.link_button("Yahoo 個股資訊", f"https://tw.stock.yahoo.com/quote/{selected}")
