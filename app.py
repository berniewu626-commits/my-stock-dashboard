import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="台股產業資金流向儀表板", layout="wide")
st.title("🔥 產業冷熱與強勢股即時追蹤")

# 建立專屬關注清單
industry_dict = {
    "半導體與晶圓代工": {"2303.TW": "聯電", "6836.TWO": "華景電"},
    "通訊網路與矽光子": {"3105.TWO": "穩懋", "3081.TWO": "聯亞", "3363.TW": "上詮"},
    "光電與被動元件": {"2489.TW": "瑞軒", "2327.TW": "國巨", "2492.TW": "華新科"}
}

# 抓取即時數據的函數
@st.cache_data(ttl=300) # 每 5 分鐘快取一次，避免 API 抓太多次被鎖
def fetch_stock_data():
    all_data = []
    for group, stocks in industry_dict.items():
        for ticker, name in stocks.items():
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period="2d")
                if len(hist) >= 2:
                    close_today = hist['Close'].iloc[-1]
                    close_yest = hist['Close'].iloc[-2]
                    vol_today = hist['Volume'].iloc[-1]
                    pct_change = ((close_today - close_yest) / close_yest) * 100
                    
                    all_data.append({
                        "族群": group,
                        "股票": name,
                        "代號": ticker,
                        "最新股價": round(close_today, 2),
                        "漲跌幅(%)": round(pct_change, 2),
                        "成交量(股)": vol_today
                    })
            except Exception:
                pass
    return pd.DataFrame(all_data)

st.write("正在從 Yahoo Finance 獲取最新市場數據...")
df = fetch_stock_data()

if not df.empty:
    st.subheader("📊 1. 產業熱力圖 (區塊大小 = 成交量，顏色 = 漲跌幅)")
    fig_treemap = px.treemap(
        df, path=['族群', '股票'], values='成交量(股)', color='漲跌幅(%)',
        color_continuous_scale=['#00ff00', 'white', '#ff0000'],
        color_continuous_midpoint=0
    )
    fig_treemap.update_layout(margin=dict(t=10, l=10, r=10, b=10))
    st.plotly_chart(fig_treemap, use_container_width=True)
    
    st.divider()
    
    selected_group = st.selectbox("🎯 2. 選擇你要深入看盤的族群：", df['族群'].unique())
    group_df = df[df['族群'] == selected_group].sort_values(by="漲跌幅(%)", ascending=False)
    
    st.dataframe(group_df[['股票', '代號', '最新股價', '漲跌幅(%)', '成交量(股)']], use_container_width=True, hide_index=True)
    
    st.write("### 📈 3. 點擊個股查看即時走勢")
    cols = st.columns(len(group_df))
    
    for idx, row in group_df.reset_index().iterrows():
        ticker = row['代號']
        stock_name = row['股票']
        
        with cols[idx]:
            with st.popover(f"🔍 {stock_name} K線"):
                st.write(f"**{stock_name} 近一個月走勢**")
                
                # 繪製 K 線圖
                stock_data = yf.download(ticker, period="1mo", interval="1d", progress=False)
                if not stock_data.empty:
                    fig_k = go.Figure(data=[go.Candlestick(
                        x=stock_data.index,
                        open=stock_data['Open'].squeeze(),
                        high=stock_data['High'].squeeze(),
                        low=stock_data['Low'].squeeze(),
                        close=stock_data['Close'].squeeze()
                    )])
                    fig_k.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0), xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig_k, use_container_width=True)
                
                raw_code = ticker.split('.')[0]
                yahoo_url = f"https://tw.stock.yahoo.com/quote/{raw_code}/technical-analysis"
                st.link_button("🌐 開啟 Yahoo 完整 K 線", yahoo_url)
else:
    st.error("目前無法獲取數據，請稍後再試。")