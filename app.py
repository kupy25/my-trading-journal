import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import time

st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key=f"final_fix_{int(time.time())}")

SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit#gid=0"
CSV_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/export?format=csv&gid=0"
PORTFOLIO_START_VAL = 44302.55 

st.markdown(f"### [🔗 מעבר לגוגל שיטס]({SHEET_URL})")

try:
    # קריאת נתונים
    df = pd.read_csv(f"{CSV_URL}&t={int(time.time())}")
    df.columns = df.columns.str.strip()

    # פונקציה לניקוי פסיקים והמרה למספר
    def clean_num(val):
        if pd.isna(val): return 0.0
        if isinstance(val, str):
            val = val.replace(',', '').replace('$', '').strip()
        return pd.to_numeric(val, errors='coerce')

    # המרת כל העמודות הרלוונטיות
    cols_to_fix = ['Qty', 'עלות כניסה', 'Exit_Price', 'PnL', 'מזומן_עדכני']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = df[col].apply(clean_num).fillna(0.0)

    # שליפת מזומן מעמודה N
    current_cash = float(df['מזומן_עדכני'].iloc[0]) if 'מזומן_עדכני' in df.columns else 0.0

    # סינון פוזיציות פתוחות
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    
    market_val_total = 0
    live_df = pd.DataFrame()

    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum'}).reset_index()
        tickers = summary['Ticker'].tolist()
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        results = []
        for _, row in summary.iterrows():
            t = row['Ticker']
            price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            val = float(price * row['Qty'])
            market_val_total += val
            results.append({'Ticker': t, 'שווי': val, 'רווח_$': val - row['עלות כניסה']})
        live_df = pd.DataFrame(results)

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${current_cash:,.2f}")
    
    total_val = market_val_total + current_cash
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.subheader("שווי תיק כולל")
    st.sidebar.title(f"${total_val:,.2f}")
    
    color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<h3 style='color:{color};'>{'+' if diff >= 0 else ''}{diff:,.2f}$</h3>", unsafe_allow_html=True)

    # --- מסך ראשי ---
    if not live_df.empty:
        st.subheader("פוזיציות פתוחות")
        st.dataframe(live_df, use_container_width=True, hide_index=True)
        
        # גרף פאי
        pie_data = pd.concat([live_df[['Ticker', 'שווי']], pd.DataFrame([{'Ticker': 'מזומן', 'שווי': current_cash}])])
        st.plotly_chart(px.pie(pie_data, values='שווי', names='Ticker', hole=0.4), use_container_width=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
