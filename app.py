import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# 設定網頁標題與寬版
st.set_page_config(page_title="暗黑風台股產業資金儀表板", layout="wide")

# ==========================================
# 需求 1：深色/暗黑背景與白色字體 (CSS 注入)
# ==========================================
st.markdown("""
    <style>
    /* 全域暗黑背景與文字顏色 */
    .stApp {
        background-color: #121212;
        color: #E0E0E0;
    }
    /* 下拉選單與輸入框暗色風格 */
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="暗黑風台股戰情室", layout="wide")

# 1. 樣式注入 (黑底白字)
st.markdown("<style>.stApp{background-color:#121212;color:#E0E0E0;} .stMetric{background-color:#1E1E1E;padding:10px;border-radius:5px;}</style>", unsafe_allow_html=True)
st.title("🖤 台股產業資金流向戰情室")

# 2. 產業與股票對照表
industry_dict = {
    "半導體與晶圓": {"2330.TW": "台積電", "2303.TW": "聯電", "5347.TWO": "世界", "6770.TW": "力積電"},
    "半導體設備": {"3131.TWO": "弘塑", "3583.TW": "辛耘", "6187.TWO": "萬潤", "6836.TWO": "華景電"},
    "矽光子網通": {"3105.TWO": "穩懋", "3081.TWO": "聯亞", "3363.TW": "上詮", "3163.TWO": "波若威"},
    "光電被動元件": {"2489.TW": "瑞軒", "2327.TW": "國巨", "2492.TW": "華新科", "3026.TW": "禾伸堂"},
    "AI伺服器代工": {"2382.TW": "廣達", "3231.TW": "緯創", "2376.TW": "技嘉", "2356.TW": "英業達"},
    "重電與散熱": {"1519.TW": "華城", "1503.TW": "士電", "3017.TW": "奇鋐", "3324.TW": "雙鴻"}
}

ticker_map = {t: {"name": n, "group": g} for g, s in industry_dict.items() for t, n in s.items()}

# 3. 歷史日期選單 (2026/01/01 起)
st.sidebar.header("📅 歷史查詢")
selected_date = st.sidebar.date_input("交易日期", value=datetime.now().date(), min_value=datetime(2026, 1, 1).date(), max_value=datetime.now().date())

@st.cache_data(ttl=300)
def get_data(target_date):
    tickers = list(ticker_map.keys())
    s_date, e_date = target_date - timedelta(days=7), target_date + timedelta(days=1)
    df_raw = yf.download(tickers, start=s_date.strftime('%Y-%m-%d'), end=e_date.strftime('%Y-%m-%d'), progress=False)
    res = []
    if not df_raw.empty and 'Close' in df_raw:
        closes, vols = df_raw['Close'], df_raw['Volume']
        valid_dates = [d for d in closes.index if d.date() <= target_date]
        if len(valid_dates) >= 2:
            t_day, y_day = valid_dates[-1], valid_dates[-2]
            for t in tickers:
                try:
                    c1, c0, v = float(closes[t].loc[t_day]), float(closes[t].loc[y_day]), int(vols[t].loc[t_day])
                    if not (pd.isna(c1) or pd.isna(c0)):
                        res.append({"族群": ticker_map[t]["group"], "股票": ticker_map[t]["name"], "代號": t, "最新股價": round(c1, 2), "漲跌幅(%)": round(((c1 - c0)/c0)*100, 2), "成交量": v})
                except Exception: pass
    return pd.DataFrame(res)

df = get_data(selected_date)

if not df.empty:
    st.caption(f"📆 查詢日期：{selected_date.strftime('%Y-%m-%d')}")
    
    # 4. 強勢股雷達 (漲幅 > 2.5%)
    st.subheader("⚡ 強勢股雷達 (漲幅 > 2.5%)")
    strong = df[df['漲跌幅(%)'] >= 2.5].sort_values(by="漲跌幅(%)", ascending=False)
    st.dataframe(strong[['族群', '股票', '代號', '最新股價', '漲跌幅(%)', '成交量']] if not strong.empty else pd.DataFrame([{"訊息": "無漲幅 > 2.5% 標的"}]), use_container_width=True, hide_index=True)

    # 5. 低彩度熱力圖 + 點擊連動
    st.subheader("📊 產業熱力圖 (點擊可切換下方族群)")
    fig = px.treemap(df, path=['族群', '股票'], values='成交量', color='漲跌幅(%)', color_continuous_scale=['#2D5A27', '#1E1E1E', '#8C2D2D'], color_continuous_midpoint=0, template="plotly_dark")
    fig.update_layout(margin=dict(t=10, l=10, r=10, b=10), paper_bgcolor="#121212", plot_bgcolor="#121212")
    
    event = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    if "selected_group" not in st.session_state:
        st.session_state["selected_group"] = df['族群'].iloc[0]
    if event and "points" in event.get("selection", {}):
        pts = event["selection"]["points"]
        if pts and pts[0].get("label") in industry_dict:
            st.session_state["selected_group"] = pts[0].get("label")

    # 6. 族群明細與 K 線展開
    all_groups = list(df['族群'].unique())
    def_idx = all_groups.index(st.session_state["selected_group"]) if st.session_state["selected_group"] in all_groups else 0
    sel_group = st.selectbox("🎯 深入研究族群：", all_groups, index=def_idx)
    
    group_df = df[df['族群'] == sel_group].sort_values(by="漲跌幅(%)", ascending=False)
    st.dataframe(group_df[['股票', '代號', '最新股價', '漲跌幅(%)', '成交量']], use_container_width=True, hide_index=True)
    
    st.write("### 📈 族群個股 K 線")
    cols = st.columns(3)
    for idx, row in group_df.reset_index().iterrows():
        with cols[idx % 3]:
            st.markdown(f"**{row['股票']} ({row['代號']})**")
            k_df = yf.download(row['代號'], start=selected_date - timedelta(days=40), end=selected_date + timedelta(days=1), progress=False)
            if not k_df.empty:
                fig_k = go.Figure(data=[go.Candlestick(x=k_df.index, open=k_df['Open'].squeeze(), high=k_df['High'].squeeze(), low=k_df['Low'].squeeze(), close=k_df['Close'].squeeze())])
                fig_k.update_layout(height=220, margin=dict(l=0, r=0, t=10, b=0), xaxis_rangeslider_visible=False, template="plotly_dark", paper_bgcolor="#121212", plot_bgcolor="#121212")
                st.plotly_chart(fig_k, use_container_width=True)
            code = row['代號'].split('.')[0]
            st.link_button("🌐 Yahoo K線", f"https://tw.stock.yahoo.com/quote/{code}/technical-analysis")
else:
    st.error("該日期無數據，請切換至其他交易日。")
