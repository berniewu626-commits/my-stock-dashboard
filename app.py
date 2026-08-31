import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="台股產業資金流向儀表板", layout="wide")
st.title("🔥 台股產業冷熱與強勢股即時追蹤")

# 1. 擴充版台股大族群字典 (可自行往下無限新增)
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

# 建立反向查詢字典，方便後續對應資料
ticker_info = {}
for group, stocks in industry_dict.items():
    for ticker, name in stocks.items():
        ticker_info[ticker] = {"name": name, "group": group}

# 2. 改用整批下載 (Batch Download) 解決速度問題
@st.cache_data(ttl=300)
def fetch_batch_data():
    all_tickers = list(ticker_info.keys())
    # 一次性向 Yahoo 抓取所有股票，大幅提升效能
    data = yf.download(all_tickers, period="2d", progress=False)
    
    results = []
    if not data.empty:
        closes = data['Close']
        volumes = data['Volume']
        
        for ticker in all_tickers:
            try:
                close_today = closes[ticker].iloc[-1]
                close_yest = closes[ticker].iloc[-2]
                vol_today = volumes[ticker].iloc[-1]
                
                # 排除無交易資料的項目
                if pd.isna(close_today) or pd.isna(close_yest):
                    continue
                    
                pct_change = ((close_today - close_yest) / close_yest) * 100
                
                results.append({
                    "族群": ticker_info[ticker]["group"],
                    "股票": ticker_info[ticker]["name"],
                    "代號": ticker,
                    "最新股價": round(float(close_today), 2),
                    "漲跌幅(%)": round(float(pct_change), 2),
                    "成交量(股)": int(vol_today)
                })
            except Exception:
                continue
    return pd.DataFrame(results)

st.write("正在從 Yahoo Finance 整批獲取最新市場數據 (約需 3~5 秒)...")
df = fetch_batch_data()

if not df.empty:
    st.subheader("📊 1. 產業熱力圖 (區塊大小 = 成交量，顏色 = 漲跌幅)")
    fig_treemap = px.treemap(
        df, path=['族群', '股票'], values='成交量(股)', color='漲跌幅(%)',
        color_continuous_scale=['#00ff00', 'white', '#ff0000'],
        color_continuous_midpoint=0,
        hover_data=['最新股價']
    )
    fig_treemap.update_layout(margin=dict(t=10, l=10, r=10, b=10))
    st.plotly_chart(fig_treemap, use_container_width=True)
    
    st.divider()
    
    selected_group = st.selectbox("🎯 2. 選擇你要深入看盤的族群：", df['族群'].unique())
    group_df = df[df['族群'] == selected_group].sort_values(by="漲跌幅(%)", ascending=False)
    
    st.dataframe(group_df[['股票', '代號', '最新股價', '漲跌幅(%)', '成交量(股)']], use_container_width=True, hide_index=True)
    
    st.write("### 📈 3. 族群個股即時 K 線 (自動展開)")
    
    # 為了版面美觀，設定每排顯示 3 檔股票的 K 線
    num_cols = 3
    cols = st.columns(num_cols)
    
    for idx, row in group_df.reset_index().iterrows():
        ticker = row['代號']
        stock_name = row['股票']
        
        # 利用餘數運算，自動將股票分配到 3 個欄位中
        col_idx = idx % num_cols
        with cols[col_idx]:
            st.markdown(f"**{stock_name} ({ticker})**")
            
            # 自動抓取並繪製 K 線圖
            stock_data = yf.download(ticker, period="1mo", interval="1d", progress=False)
            if not stock_data.empty:
                fig_k = go.Figure(data=[go.Candlestick(
                    x=stock_data.index,
                    open=stock_data['Open'].squeeze(),
                    high=stock_data['High'].squeeze(),
                    low=stock_data['Low'].squeeze(),
                    close=stock_data['Close'].squeeze()
                )])
                fig_k.update_layout(height=250, margin=dict(l=0, r=0, t=10, b=0), xaxis_rangeslider_visible=False)
                st.plotly_chart(fig_k, use_container_width=True)
            
            raw_code = ticker.split('.')[0]
            yahoo_url = f"https://tw.stock.yahoo.com/quote/{raw_code}/technical-analysis"
            st.link_button(f"🌐 Yahoo 完整線圖", yahoo_url)
            
            st.write("---") # 加上底部分隔線讓排版更俐落
else:
    st.error("目前無法獲取數據，請稍後再試。")
