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
    div[data-baseweb="select"] > div {
        background-color: #1E1E1E !important;
        color: #FFFFFF !important;
        border-color: #333333 !important;
    }
    /* 卡片與容器樣式 */
    .stMetric {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #333333;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🖤 台股產業資金流向與強勢股戰情室")

# 1. 擴充版產業字典
industry_dict = {
    "半導體與晶圓代工": {"2330.TW": "台積電", "2303.TW": "聯電", "5347.TWO": "世界", "6770.TW": "力積電"},
    "半導體設備與耗材": {"3131.TWO": "弘塑", "3583.TW": "辛耘", "6187.TWO": "萬潤", "6836.TWO": "華景電", "3680.TW": "家登"},
    "通訊網路與矽光子": {"3105.TWO": "穩懋", "3081.TWO": "聯亞", "3363.TW": "上詮", "3163.TWO": "波若威", "4979.TW": "華星光"},
    "光電與被動元件": {"2489.TW": "瑞軒", "2327.TW": "國巨", "2492.TW": "華新科", "3026.TW": "禾伸堂", "2428.TW": "興勤"},
    "AI 伺服器與代工": {"2382.TW": "廣達", "3231.TW": "緯創", "2376.TW": "技嘉", "2356.TW": "英業達", "3232.TW": "智易"},
    "重電與綠能": {"1503.TW": "士電", "1504.TW": "東元", "1513.TW": "中興電", "1514.TW": "亞力", "1519.TW": "華城"},
    "散熱族群": {"3017.TW": "奇鋐", "3324.TW": "雙鴻", "2421.TW": "建準", "3653.TW": "健策"},
    "機器人與智動化": {"2359.TW": "所羅門", "2365.TW": "昆盈", "2373.TW": "震旦行", "6188.TWO": "廣明"},
    "航運與散裝": {"2603.TW": "長榮", "2609.TW": "陽明", "2615.TW": "萬海", "2618.TW": "長榮航", "2606.TW": "裕民"}
}

ticker_info = {}
for group, stocks in industry_dict.items():
    for ticker, name in stocks.items():
        ticker_info[ticker] = {"name": name, "group": group}

# ==========================================
# 需求 5：每日歷史資料庫查閱 (從 2026/01/01 起)
# ==========================================
st.sidebar.header("📅 歷史數據查詢庫")
start_of_year = datetime(2026, 1, 1).date()
today = datetime.now().date()

selected_date = st.sidebar.date_input(
    "選擇要調閱的交易日期",
    value=today,
    min_value=start_of_year,
    max_value=today
)

@st.cache_data(ttl=300)
def fetch_data_by_date(target_date):
    all_tickers = list(ticker_info.keys())
    # 多抓 5 天以防遇到假日
    start_str = (target_date - timedelta(days=7)).strftime('%Y-%m-%d')
    end_str = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')
    
    data = yf.download(all_tickers, start=start_str, end=end_str, progress=False)
    
    results = []
    if not data.empty:
        closes = data['Close']
        volumes = data['Volume']
        
        # 篩選出不大於 target_date 的最新交易日
        valid_dates = [d for d in closes.index if d.date() <= target_date]
        if len(valid_dates) >= 2:
            t_day = valid_dates[-1]
            y_day = valid_dates[-2]
            
            for ticker in all_tickers:
                try:
                    c_today = closes[ticker].loc[t_day]
                    c_yest = closes[ticker].loc[y_day]
                    v_today = volumes[ticker].loc[t_day]
                    
                    if pd.isna(c_today) or pd.isna(c_yest):
                        continue
                        
                    pct_change = ((c_today - c_yest) / c_yest) * 100
                    
                    results.append({
                        "族群": ticker_info[ticker]["group"],
                        "股票": ticker_info[ticker]["name"],
                        "代號": ticker,
                        "最新股價": round(float(c_today), 2),
                        "漲跌幅(%)": round(float(pct_change), 2),
                        "成交量(股)": int(v_today)
                    })
                except Exception:
                    continue
    return pd.DataFrame(results)

df = fetch_data_by_date(selected_date)

if not df.empty:
    # 顯示目前查閱的日期
    st.info(f"📆 目前顯示資料時間：**{selected_date.strftime('%Y-%m-%d')}**")

    # ==========================================
    # 需求 4：今日觀察股票候選 (自動選出強勢個股)
    # ==========================================
    st.subheader("⚡ 強勢個股觀察雷達 (當日漲幅 > 2.5% 精選)")
    strong_stocks = df[df['漲跌幅(%)'] >= 2.5].sort_values(by="漲跌幅(%)", ascending=False)
    
    if not strong_stocks.empty:
        st.dataframe(
            strong_stocks[['族群', '股票', '代號', '最新股價', '漲跌幅(%)', '成交量(股)']],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.caption("該交易日暫無漲幅 > 2.5% 的
