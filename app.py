import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import time

st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key=f"cash_fix_{int(time.time())}")

SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit#gid=0"
# קישור הורדה ישיר
CSV_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/export?format=csv&gid=0"

st.markdown(f"### [🔗 לחץ כאן למעבר לגוגל שיטס]({SHEET_URL})")

try:
    # קריאה עם עוקף מטמון
    df = pd.read_csv(f"{CSV_URL}&cache={int(time.time())}")
    
    # ניקוי שמות עמודות מרווחים ותווים נסתרים
    df.columns = df.columns.str.strip().str.replace('\n', '').str.replace('\r', '')

    # --- איתור עמודת המזומן ---
    # מחפש עמודה שמכילה את המילה 'מזומן'
    cash_col = [c for c in df.columns if 'מזומן' in c]
    
    if cash_col:
        # לוקח את הערך הראשון בעמודה שמצאנו (N2)
        raw_cash = df[cash_col[0]].iloc[0]
        current_cash = pd.to_numeric(raw_cash, errors='coerce')
        if pd.isna(current_cash): current_cash = 0.0
    else:
        current_cash = 0.0
        st.warning("לא מצאתי עמודה עם המילה 'מזומן' בגיליון")

    # המרת שאר העמודות
    for col in ['Qty', 'עלות כניסה', 'Exit_Price']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # סינון פוזיציות
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    
    market_val_total = 0
    live_list = []
    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum'}).reset_index()
        tickers = summary['Ticker'].tolist()
        data = yf.download(tickers, period="1d", progress=False)['Close']
        for _, row in summary.iterrows():
            t = row['Ticker']
            price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            val = float(price * row['Qty'])
            market_val_total += val
            live_list.append({'Ticker': t, 'שווי': val})
        live_df = pd.DataFrame(live_list)

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    # כאן יופיע ה-8,377.65
    st.sidebar.metric("מזומן פנוי", f"${current_cash:,.2f}")
    
    total_val = market_val_total + current_cash
    st.sidebar.subheader("שווי תיק כולל")
    st.sidebar.title(f"${total_val:,.2f}")

    # טאב פוזיציות
    if not open_trades.empty:
        st.dataframe(live_df, use_container_width=True, hide_index=True)
        # גרף פאי שכולל את המזומן
        pie_data = pd.concat([live_df, pd.DataFrame([{'Ticker': 'מזומן', 'שווי': current_cash}])])
        st.plotly_chart(px.pie(pie_data, values='שווי', names='Ticker', hole=0.4), use_container_width=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
