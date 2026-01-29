import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import time

st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key=f"debug_fix_{int(time.time())}")

SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit#gid=0"
CSV_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/export?format=csv&gid=0"

st.markdown(f"### [🔗 מעבר לגיליון גוגל שיטס]({SHEET_URL})")

try:
    # קריאת הנתונים
    df = pd.read_csv(f"{CSV_URL}&cache={int(time.time())}")
    
    # ניקוי שמות עמודות
    original_columns = list(df.columns)
    df.columns = df.columns.str.strip()

    # --- לוח בקרה בסיידבר לאבחון שגיאות ---
    st.sidebar.header("🔍 לוח בקרה (דיאגנוסטיקה)")
    st.sidebar.write("העמודות שהקוד מזהה:")
    st.sidebar.write(df.columns.tolist())
    
    # חיפוש עמודת מזומן
    cash_col = [c for c in df.columns if 'מזומן' in c]
    
    if cash_col:
        st.sidebar.success(f"נמצאה עמודה: {cash_col[0]}")
        raw_val = df[cash_col[0]].iloc[0]
        st.sidebar.write(f"ערך גולמי בתא הראשון: {raw_val}")
        current_cash = pd.to_numeric(raw_cash := raw_val, errors='coerce')
    else:
        st.sidebar.error("❌ לא נמצאה עמודה עם המילה 'מזומן'")
        current_cash = 0.0

    # המרת שאר הנתונים
    for col in ['Qty', 'עלות כניסה', 'Exit_Price', 'PnL']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # הפרדה לפתוחות וסגורות
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    
    # חישוב שווי שוק
    market_val_total = 0
    if not open_trades.empty:
        tickers = open_trades['Ticker'].unique().tolist()
        data = yf.download(tickers, period="1d", progress=False)['Close']
        for t in tickers:
            qty = open_trades[open_trades['Ticker'] == t]['Qty'].sum()
            price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            market_val_total += (price * qty)

    # --- תצוגת תוצאות ---
    st.sidebar.divider()
    st.sidebar.metric("מזומן שזוהה", f"${current_cash:,.2f}")
    st.sidebar.metric("שווי שוק פוזיציות", f"${market_val_total:,.2f}")
    
    st.title(f"שווי תיק כולל: ${market_val_total + current_cash:,.2f}")
    
    if not open_trades.empty:
        st.subheader("פוזיציות פתוחות")
        st.dataframe(open_trades[['Ticker', 'Qty', 'עלות כניסה']], use_container_width=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
