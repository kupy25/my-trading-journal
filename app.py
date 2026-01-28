import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
import plotly.express as px

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק ומעקב טריידים - 2026")

SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()

    # טיפול בתאריכים
    for date_col in ['Entry_Date', 'Exit_Date']:
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce').dt.date

    # המרת עמודות למספרים
    numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'עלות יציאה', 'PnL']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # הפרדה לפתוחים וסגורים
    open_trades = df[df['Exit_Price'] == 0].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy().sort_values(by='Exit_Date', ascending=False)

    # חישוב PnL ממומש (Realized)
    total_realized_pnl = closed_trades['PnL'].sum()

    # --- משיכת נתוני שוק ---
    open_tickers = [str(t).strip().upper() for t in open_trades['Ticker'].dropna().unique()]
    market_data = {}
    if open_tickers:
        data_dl = yf.download(open_tickers, period="1y", group_by='ticker', progress=False)
        for t in open_tickers:
            try:
                t_hist = data_dl[t] if len(open_tickers) > 1 else data_dl
                market_data[t] = {
                    'curr': t_hist['Close'].iloc[-1],
                    'ma150': t_hist['Close'].rolling(window=150).mean().iloc[-1]
                }
            except: continue

    # --- Sidebar Summary ---
    st.sidebar.header("⚙️ סיכום ביצועים")
    
    # הצגת PnL ממומש (Realized)
    r_color = "#00c853" if total_realized_pnl >= 0 else "#ff4b4b"
    st.sidebar.metric("PnL ממומש (סגור)", f"${total_realized_pnl:,.2f}", delta_color="normal")
    st.sidebar.markdown(f"<p style='color:{r_color}; font-size:12px; margin-top:-15px;'>סה\"כ רווח/הפסד מטריידים שנסגרו</p>", unsafe_allow_html=True)
    
    st.sidebar.divider()
    
    # חישוב PnL לא ממומש (Live)
    total_unrealized_pnl = 0
    market_value_stocks = 0
    for _, row in open_trades.iterrows():
        t = str(row['Ticker']).strip().upper()
        if t in market_data:
            curr = market_data[t]['curr']
            total_unrealized_pnl += (curr - row['Entry_Price']) * row['Qty']
            market_value_stocks += curr * row['Qty']

    u_color = "#00c853" if total_unrealized_pnl >= 0 else "#ff4b4b"
    st.sidebar.metric("PnL לא ממומש (לייב)", f"${total_unrealized_pnl:,.2f}")
    
    st.sidebar.divider()
    st.link_button("📂 פתח גיליון גוגל לעדכון", SHEET_URL, use_container_width=True, type="primary")

    # --- תצוגה מרכזית ---
    tab1, tab2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])

    with tab1:
        st.subheader("פוזיציות פעילות")
        cols_open = ['Ticker', 'Entry_Date', 'Qty', 'Entry_Price', 'עלות כניסה', 'סיבת כניסה']
        st.dataframe(open_trades[[c for c in cols_open if c in open_trades.columns]], use_container_width=True)

    with tab2:
        st.subheader("היסטוריית עסקאות")
        cols_closed = [
            'Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'Entry_Price', 
            'עלות כניסה', 'Exit_Price', 'עלות יציאה', 'PnL', 'סיבת יציאה'
        ]
        st.dataframe(closed_trades[[c for c in cols_closed if c in closed_trades.columns]], use_container_width=True)

except Exception as e:
    st.error(f"שגיאה בעדכון הנתונים: {e}")
