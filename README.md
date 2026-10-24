# 台股產業資金流向戰情室

保留原有暗黑介面、28 族群、強勢股雷達、熱力圖、族群明細、個股 K 線與 Yahoo 連結。

## 啟動與測試

建議 Python 3.10 以上（exchange-calendars 4.13.2 的最低版本要求）。

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
python -m unittest discover -s tests -v
```

測試使用固定時間與模擬行情，不會連線下載 Yahoo 報價。

## 日期行為

- 查詢預設值與上限使用 `Asia/Taipei`；保留 2026-01-01 的查詢下限。
- 查詢日期、實際資料日期、漲跌比較基準日分別顯示；取得時間是下載完成時間，不是假定的行情發布時間。
- 從查詢日往前抓 30 個日曆日，若不足兩個有效價格日，再擴至 90 天；下載 end 仍是查詢日加一天，因 yfinance 的 end 不包含當天。
- 排序、去除重複日期、排除未來資料及全空值／非正有限價格日期。含時區索引先轉台灣時間；無時區日線索引按當地日期處理。
- 全部股票使用相同兩個資料日；缺少有效價格或成交量的股票排除並顯示清單，不自行補上更舊價格。成交量為零仍可保留。
- 使用本機 `exchange-calendars` 的 XTAI 日曆識別週末、例假日與最近排定交易日；這是排程參考，不是即時交易所公告。日曆失效時仍依報價回溯，但明確提示無法確認休市／延遲。
- 當日 09:00 前提示尚未開盤；09:00–13:30 提示盤中資料未完整；收盤後提示仍可能補登。15:00 前缺當日資料顯示等待提示，15:00 起改為可能延遲警告。**15:00 是本程式提示門檻，並非 Yahoo 的交付承諾。** 缺少更早排定交易日資料時仍警告。
- 若兩個比較資料日中間缺少排定交易日，顯示「區間變動，不是單日漲跌」。
- K 線上限改用實際資料日，避免表格採前一日、圖卻多出當日；K 線獨立下載失敗不阻斷主畫面。
- 報價快取維持 300 秒；「重新整理資料」清除所選日期的快取。提示依每次頁面執行時的台灣時間重新判斷；本次未新增定時自動刷新。

## 修改位置

| 檔案 | 關鍵位置 |
| --- | --- |
| `app.py` | `today_tw` / 日期選單、`get_data`、日期與資料品質提示、K 線下載上限 |
| `trading_dates.py` | `normalize_daily_data`、`select_snapshot`、`download_snapshot`、`calendar_sessions`、`date_notices` |
| `requirements.txt` | 新增 `exchange-calendars>=4.13.2,<5`、`tzdata` |
| `tests/test_trading_dates.py` | 日期邊界、非交易日、缺漏及提示測試 |
| `tests/test_app.py` | Streamlit 畫面、族群切換、快取與刷新、錯誤處理測試 |

## 風險與維護

- 30／90 天下載量比原本 7 天多；不足兩日的情況最多下載兩次。手動刷新會增加 Yahoo 請求，仍可能被限流。
- 日曆套件可能尚未收錄颱風等臨時休市；因此缺資料只提示「可能延遲、缺漏或臨時休市」，不直接斷言供應商延遲。跨年度須維護套件及核對官方日曆。
- 部分股票缺漏時排行／熱力圖僅代表可用標的；一檔先更新即可能成為最新資料日，其他未更新股票會被排除並明示。這不代表全市場已更新。
- 保留既有盤中可查看當日日線的行為，但標示尚未完整；盤後價格仍可能被 Yahoo 修訂。K 線與主表為分開請求，可能遇到不同時間的資料修訂。
- 加入日曆套件會增加安裝依賴與首次載入成本。原有 Streamlit、yfinance、pandas、Plotly 的版本策略未改動。

## 參考來源

- [TWSE 市場開休市日期](https://www.twse.com.tw/zh/trading/holiday.html)
- [TWSE 2026 年開休市表（查核春節 2/12–2/22 休市、2/23 開市）](https://www.twse.com.tw/holidaySchedule/holidaySchedule?response=html)
- [exchange_calendars XTAI 實作](https://github.com/gerrymanoim/exchange_calendars/blob/master/exchange_calendars/exchange_calendar_xtai.py)
- [yfinance.download 參數與 end 不包含當天的定義](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html)
