import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון אוטומטי (10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key="back_to_basics_refresh")

# 2. נתוני בסיס (כאן אתה מעדכן את המזומן כשאתה קונה/מוכר)
CASH_NOW = 3755.0  # המזומן הפנוי שלך כרגע
PORTFOLIO_START_VAL = 44302.55 # שווי התיק ביום פתיחת היומן

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

# 3. חיבור לגיליון
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    
    # המרת עמודות למספרים
    for col in ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # סינון פוזיציות
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # חישוב עמלות
    fees_open = open_trades['Qty'].apply(get_fee).sum()
    fees_closed = (closed_trades['Qty'].apply(get_fee).sum() * 2)
    total_fees = fees_open + fees_closed

    # נתוני לייב
    market_val_total = 0
    live_list = []

    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum'}).reset_index()
        tickers = list(summary['Ticker'].unique())
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        for _, row in summary.iterrows():
            t = row['Ticker']
            price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            val = price * row['Qty']
            market_val_total += val
            
            avg_cost = row['עלות כניסה'] / row['Qty']
            pnl_usd = (val - row['עלות כניסה']) - get_fee(row['Qty'])
            pnl_pct = ((price - avg_cost) / avg_cost) * 100
            live_list.append({'Ticker': t, 'כמות': row['Qty'], 'שווי_שוק': val, 'רווח_דולרי': pnl_usd, 'רווח_באחוזים': pnl_pct})
        
        live_df = pd.DataFrame(live_list)

    # --- SIDEBAR (ניהול חשבון) ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${CASH_NOW:,.2f}")
    
    total_val = market_val_total + CASH_NOW
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.subheader("שווי תיק כולל")
    st.sidebar.title(f"${total_val:,.2f}")
    
    color = "green" if diff >= 0 else "red"
    st.sidebar.markdown(f"<p style='color:{color}; font-size: 20px; font-weight: bold;'>רווח/הפסד: ${diff:,.2f}</p>", unsafe_allow_html=True)
    st.sidebar.write(f"עמלות מצטברות: ${total_fees:,.2f}")

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades.empty:
            st.dataframe(live_df, use_container_width=True, hide_index=True)
            st.divider()
            pie_data = pd.concat([live_df[['Ticker', 'שווי_שוק']].rename(columns={'שווי_שוק': 'Value'}), 
                                 pd.DataFrame([{'Ticker': 'מזומן', 'Value': CASH_NOW}])])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Ticker', hole=0.4, title="פיזור תיק"), use_container_width=True)

    with t2:
        if not closed_trades.empty:
            st.subheader(f"רווח ממומש כולל: ${closed_trades['PnL'].sum():,.2f}")
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL', 'סיבת כניסה', 'סיבת יציאה']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
