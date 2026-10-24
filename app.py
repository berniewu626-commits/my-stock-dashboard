import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from trading_dates import (
    calendar_sessions, date_notices, download_snapshot,
    normalize_daily_data, taipei_now,
)

st.set_page_config(page_title="暗黑風台股戰情室", layout="wide")

st.markdown("""
<style>
.stApp { background-color: #121212; color: #E0E0E0; }
.stMetric { background-color: #1E1E1E; padding: 10px; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

st.title("🖤 台股產業資金流向戰情室 (28大族群版)")

# 擴充為 28 個族群，約 115 檔指標股
industry_dict = {
    "半導體與晶圓": {"2330.TW": "台積電", "2303.TW": "聯電", "5347.TWO": "世界", "6770.TW": "力積電"},
    "IC設計": {"2454.TW": "聯發科", "3034.TW": "聯詠", "2379.TW": "瑞昱", "3443.TW": "創意"},
    "半導體設備": {"3131.TWO": "弘塑", "3583.TW": "辛耘", "6187.TWO": "萬潤", "6836.TWO": "華景電", "3680.TW": "家登"},
    "矽光子網通": {"3105.TWO": "穩懋", "3081.TWO": "聯亞", "3363.TW": "上詮", "3163.TWO": "波若威", "4979.TW": "華星光"},
    "光電被動元件": {"2489.TW": "瑞軒", "2327.TW": "國巨", "2492.TW": "華新科", "3026.TW": "禾伸堂"},
    "AI伺服器代工": {"2382.TW": "廣達", "3231.TW": "緯創", "2376.TW": "技嘉", "2356.TW": "英業達", "6669.TW": "緯穎"},
    "散熱族群": {"3017.TW": "奇鋐", "3324.TW": "雙鴻", "2421.TW": "建準", "3653.TW": "健策"},
    "重電與綠能": {"1519.TW": "華城", "1503.TW": "士電", "1513.TW": "中興電", "1514.TW": "亞力"},
    "機器人與智動化": {"2359.TW": "所羅門", "2365.TW": "昆盈", "6188.TWO": "廣明", "1590.TW": "亞德客-KY"},
    "航運散裝": {"2603.TW": "長榮", "2609.TW": "陽明", "2615.TW": "萬海", "2618.TW": "長榮航", "2606.TW": "裕民"},
    "金融保險": {"2881.TW": "富邦金", "2882.TW": "國泰金", "2891.TW": "中信金", "2886.TW": "兆豐金"},
    "營建資產": {"2542.TW": "興富發", "5522.TW": "遠雄", "2520.TW": "冠德", "2548.TW": "華固"},
    "生技醫療": {"6472.TW": "保瑞", "6446.TWO": "藥華藥", "1795.TW": "美時", "4147.TWO": "中裕"},
    "汽車與零組件": {"2207.TW": "和泰車", "2201.TW": "裕隆", "1319.TW": "東陽", "1522.TW": "堤維西"},
    "鋼鐵工業": {"2002.TW": "中鋼", "2014.TW": "中鴻", "2027.TW": "大成鋼", "9958.TW": "世紀鋼"},
    "塑膠化學": {"1301.TW": "台塑", "1303.TW": "南亞", "1326.TW": "台化", "1304.TW": "台聚"},
    "紡織纖維": {"1476.TW": "儒鴻", "1477.TW": "聚陽", "1402.TW": "遠東新", "1440.TW": "南紡"},
    "觀光餐飲": {"2727.TW": "王品", "2707.TW": "晶華", "2731.TW": "雄獅", "2748.TW": "雲品"},
    "電腦與IPC": {"2395.TW": "研華", "6414.TW": "樺漢", "2353.TW": "宏碁", "2357.TW": "華碩"},
    "面板與光電": {"2409.TW": "友達", "3481.TW": "群創", "6116.TW": "彩晶", "8215.TW": "明基材"},
    "PCB印刷電路板": {"3037.TW": "欣興", "3189.TW": "景碩", "8046.TW": "南電", "2313.TW": "華通"},
    "銅箔基板CCL": {"2383.TW": "台光電", "6213.TW": "聯茂", "6274.TW": "台燿", "8358.TWO": "金居"},
    "記憶體與模組": {"2408.TW": "南亞科", "2344.TW": "華邦電", "3260.TW": "威剛", "8299.TWO": "群聯"},
    "遊戲與文創": {"5478.TWO": "智冠", "3293.TW": "鈊象", "6180.TWO": "橘子", "3083.TWO": "網龍"},
    "安控與通訊": {"3356.TW": "奇偶", "3454.TW": "晶睿", "3491.TW": "昇達科", "6285.TW": "啟碁"},
    "電子通路": {"3702.TW": "大聯大", "3036.TW": "文曄", "2347.TW": "聯強", "5434.TW": "崇越"},
    "綠能環保": {"6806.TW": "森崴能源", "6869.TW": "雲豹能源", "6873.TW": "泓德能源", "9955.TW": "佳龍"},
    "網通設備": {"2345.TW": "智邦", "3596.TW": "智易", "3380.TW": "明泰", "2419.TW": "仲琦"}
}

ticker_map = {t: {"name": n, "group": g} for g, s in industry_dict.items() for t, n in s.items()}

today_tw = taipei_now().date()
st.sidebar.header("📅 歷史查詢")
selected_date = st.sidebar.date_input(
    "查詢日期（台灣時間）", 
    value=today_tw, 
    min_value=datetime(2026, 1, 1).date(), 
    max_value=today_tw
)

@st.cache_data(ttl=300)
def get_data(target_date):
    return download_snapshot(target_date, ticker_map, yf.download)


if st.sidebar.button("🔄 重新整理資料"):
    get_data.clear(selected_date)
st.sidebar.caption("報價快取最多 5 分鐘；重新整理可立即重抓。")

st.write("正在獲取 28 大族群資料，請稍候...")
st.caption(f"📆 查詢日期：{selected_date:%Y-%m-%d}（Asia/Taipei）")
try:
    df, data_info = get_data(selected_date)
except Exception:
    st.error("行情下載失敗，無法判斷是否休市；請稍後按「重新整理資料」重試。")
    st.stop()

actual_date = data_info["actual_date"]
previous_date = data_info["previous_date"]
actual_label = actual_date.isoformat() if actual_date else "無可用資料"
previous_label = previous_date.isoformat() if previous_date else "不足兩個資料日"
st.caption(f"📊 實際資料日期：{actual_label} ｜ 漲跌比較基準日：{previous_label}")
st.caption(f"取得時間：{data_info['fetched_at']:%Y-%m-%d %H:%M:%S}（台灣時間，非行情更新時間）｜來源：Yahoo 日線，非即時行情")
for level, message in date_notices(
    selected_date, actual_date, previous_date, taipei_now(),
    calendar_sessions(selected_date.year),
):
    getattr(st, level)(message)

if data_info["excluded"]:
    st.warning(f"{len(data_info['excluded'])}/{len(ticker_map)} 檔缺少共同資料日的有效價格或成交量，已排除，未混用舊資料。族群排行與熱力圖可能不完整。")
    with st.expander("查看未納入的股票"):
        st.write("、".join(data_info["excluded"]))

if not df.empty:
    st.subheader("⚡ 強勢股雷達 (漲幅 > 2.5%)")
    strong = df[df['漲跌幅(%)'] >= 2.5].sort_values(by="漲跌幅(%)", ascending=False)
    
    if not strong.empty:
        st.dataframe(strong[['族群', '股票', '代號', '最新股價', '漲跌幅(%)', '成交量']], use_container_width=True, hide_index=True)
    else:
        st.dataframe(pd.DataFrame([{"訊息": "無漲幅 > 2.5% 標的"}]), use_container_width=True, hide_index=True)

    st.subheader("📊 產業熱力圖 (點擊可切換下方族群)")
    fig = px.treemap(
        df, path=['族群', '股票'], values='成交量', color='漲跌幅(%)', 
        color_continuous_scale=['#2D5A27', '#1E1E1E', '#8C2D2D'], 
        color_continuous_midpoint=0, template="plotly_dark"
    )
    fig.update_layout(margin=dict(t=10, l=10, r=10, b=10), paper_bgcolor="#121212", plot_bgcolor="#121212")
    
    event = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    if "selected_group" not in st.session_state:
        st.session_state["selected_group"] = df['族群'].iloc[0]
        
    if event and "points" in event.get("selection", {}):
        pts = event["selection"]["points"]
        if pts and pts[0].get("label") in industry_dict:
            st.session_state["selected_group"] = pts[0].get("label")

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
            
            k_start = actual_date - timedelta(days=40)
            k_end = actual_date + timedelta(days=1)
            try:
                k_df = yf.download(row['代號'], start=k_start.strftime('%Y-%m-%d'), end=k_end.strftime('%Y-%m-%d'), interval="1d", auto_adjust=True, progress=False)
                k_df = normalize_daily_data(k_df, actual_date)
                if isinstance(k_df.columns, pd.MultiIndex):
                    k_df.columns = k_df.columns.get_level_values(0)
            except Exception:
                k_df = pd.DataFrame()
            if k_df.empty:
                st.caption("K 線暫無可用資料，請稍後重試。")
            else:
                st.caption(f"K 線資料截至 {k_df.index[-1]:%Y-%m-%d}")
                if k_df.index[-1].date() < actual_date:
                    st.warning("K 線尚未更新至上方行情資料日。")
            
            if not k_df.empty:
                fig_k = go.Figure(data=[go.Candlestick(
                    x=k_df.index, 
                    open=k_df['Open'], 
                    high=k_df['High'], 
                    low=k_df['Low'], 
                    close=k_df['Close']
                )])
                fig_k.update_layout(
                    height=220, margin=dict(l=0, r=0, t=10, b=0), 
                    xaxis_rangeslider_visible=False, template="plotly_dark", 
                    paper_bgcolor="#121212", plot_bgcolor="#121212"
                )
                st.plotly_chart(fig_k, use_container_width=True, key=f"kline-{row['代號']}")
                
            code = row['代號'].split('.')[0]
            st.link_button("🌐 Yahoo K線", f"https://tw.stock.yahoo.com/quote/{code}/technical-analysis")
else:
    st.error(f"回查 {data_info['lookback_days']} 天後，仍無法取得共同兩個資料日的有效價格及成交量；未計算漲跌幅。請重新整理或改選日期。")

