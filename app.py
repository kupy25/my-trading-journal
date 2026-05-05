import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=15000, key="datarefresh")

# --- נתונים להזנה ידנית במקרה של סטייה ---
CASH_VAL_USER = 12298.89  # כאן תעדכן את המזומן הפנוי שאתה רואה בברוקר
PORTFOLIO_START_VAL = 44302.55 
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

# 2. חיבור וקריאת נתונים
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    
    # ניקוי נתונים
    for col in ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # הפרדה לפוזיציות
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    market_val_total = 0
    live_list = []

    # חישוב מחירים חיים
    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum', 'סיבת כניסה': 'first'}).reset_index()
        tickers = list(summary['Ticker'].unique())
        
        # הורדת נתונים מ-yfinance
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        for _, row in summary.iterrows():
            t = row['Ticker']
            try:
                # חילוץ מחיר אחרון
                if len(tickers) > 1:
                    current_price = data[t].dropna().iloc[-1]
                else:
                    current_price = data.dropna().iloc[-1]
                
                current_val = current_price * row['Qty']
                market_val_total += current_val
                
                cost = row['עלות כניסה']
                pnl_usd = (current_val - cost) - get_fee(row['Qty'])
                pnl_pct = ((current_val / cost) - 1) * 100 if cost != 0 else 0
                
                live_list.append({
                    'Ticker': t, 'כמות': row['Qty'], 'שווי נוכחי': current_val, 
                    'רווח $': pnl_usd, 'רווח %': pnl_pct, 'סיבת כניסה': row['סיבת כניסה']
                })
            except: continue

    # --- חישובי שורה תחתונה ---
    # שווי תיק כולל = מזומן פנוי + שווי שוק של המניות הפתוחות
    total_portfolio_live = CASH_VAL_USER + market_val_total
    total_pnl_all_time = total_portfolio_live - PORTFOLIO_START_VAL

    # --- SIDEBAR ---
    st.sidebar.header("💰 מצב חשבון")
    st.sidebar.metric("מזומן פנוי (סטטי)", f"${CASH_VAL_USER:,.2f}")
    st.sidebar.metric("שווי מניות (Live)", f"${market_val_total:,.2f}")
    
    st.sidebar.divider()
    st.sidebar.subheader("שווי תיק כולל (Live)")
    st.sidebar.title(f"${total_portfolio_live:,.2f}")
    
    color = "#00c853" if total_pnl_all_time >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{color}; font-size: 24px; font-weight: bold;'>{'+' if total_pnl_all_time >= 0 else ''}{total_pnl_all_time:,.2f}$</p>", unsafe_allow_html=True)

    # --- תצוגה ראשית ---
    st.title("📊 יומן המסחר של אבי")
    
    tab1, tab2 = st.tabs(["📈 פוזיציות פתוחות", "📜 היסטוריה"])
    
    with tab1:
        if live_list:
            live_df = pd.DataFrame(live_list)
            st.dataframe(live_df.style.format({
                'שווי נוכחי': "{:,.2f}$", 
                'רווח $': "{:,.2f}$", 
                'רווח %': "{:.2f}%"
            }), use_container_width=True, hide_index=True)
            
            # גרף פאי
            pie_data = pd.DataFrame([
                {'Category': 'מזומן פנוי', 'Value': CASH_VAL_USER},
                {'Category': 'מניות (בסיכון)', 'Value': market_val_total}
            ])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Category', title="חלוקת הון"), use_container_width=True)
        else:
            st.info("אין פוזיציות פתוחות כרגע.")

    with tab2:
        if not closed_trades.empty:
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'PnL']].sort_values('Exit_Date', ascending=False), use_container_width=True)

except Exception as e:
    st.error(f"קרתה שגיאה: {e}")
