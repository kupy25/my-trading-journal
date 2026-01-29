import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import time

# 1. הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key=f"pnl_summary_v1_{int(time.time())}")

# --- הגדרות ה"עוגן" ---
ANCHOR_CASH = 8377.65 
ANCHOR_DATE = pd.to_datetime("2026-01-29")
PORTFOLIO_START_VAL = 44302.55 
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit#gid=0"

def clean_numeric(val):
    if pd.isna(val): return 0.0
    if isinstance(val, str):
        val = val.replace(',', '').replace('$', '').strip()
    return pd.to_numeric(val, errors='coerce')

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(spreadsheet=SHEET_URL, ttl="0")
    df.columns = df.columns.str.strip()
    
    # המרת תאריכים
    for date_col in ['Entry_Date', 'Exit_Date']:
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

    # ניקוי מספרים
    cols_to_clean = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']
    for col in cols_to_clean:
        if col in df.columns:
            df[col] = df[col].apply(clean_numeric).fillna(0)

    # --- חישוב מזומן אוטומטי ---
    new_buys = df[(df['Entry_Date'] > ANCHOR_DATE)]
    cash_out = (new_buys['Qty'] * new_buys['Entry_Price']).sum() + new_buys['Qty'].apply(get_fee).sum()

    new_sells = df[(df['Exit_Date'] > ANCHOR_DATE)]
    cash_in = (new_sells['Qty'] * new_sells['Exit_Price']).sum() - new_sells['Qty'].apply(get_fee).sum()

    calculated_cash = ANCHOR_CASH - cash_out + cash_in

    # --- פוזיציות פתוחות ---
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull())].copy()
    market_val_total = 0
    live_df = pd.DataFrame()

    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum', 'סיבת כניסה': 'first'}).reset_index()
        tickers = summary['Ticker'].tolist()
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        res = []
        for _, row in summary.iterrows():
            t = row['Ticker']
            price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            val = price * row['Qty']
            market_val_total += val
            avg_cost = row['עלות כניסה'] / row['Qty']
            res.append({
                'Ticker': t, 'כמות': row['Qty'], 'שווי שוק': val, 
                'רווח $': (val - row['עלות כניסה']) - get_fee(row['Qty']),
                'רווח %': ((price - avg_cost) / avg_cost) * 100,
                'סיבת כניסה': row['סיבת כניסה']
            })
        live_df = pd.DataFrame(res)

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן מחושב", f"${calculated_cash:,.2f}")
    
    total_val = market_val_total + calculated_cash
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.subheader("שווי תיק כולל")
    st.sidebar.title(f"${total_val:,.2f}")
    
    pnl_color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{pnl_color}; font-size: 20px; font-weight: bold;'>{'+' if diff >= 0 else ''}{diff:,.2f}$</p>", unsafe_allow_html=True)

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    st.link_button("📂 פתח גיליון גוגל שיטס", SHEET_URL)
    
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not live_df.empty:
            st.dataframe(live_df.style.format({'שווי שוק': '${:,.2f}', 'רווח $': '${:,.2f}', 'רווח %': '{:.2f}%'}), use_container_width=True, hide_index=True)
            st.divider()
            pie_data = pd.concat([live_df[['Ticker', 'שווי שוק']].rename(columns={'שווי שוק': 'Value'}), 
                                 pd.DataFrame([{'Ticker': 'מזומן', 'Value': calculated_cash}])])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Ticker', hole=0.4, title="פיזור הון"), use_container_width=True)

    with t2:
        closed_trades = df[df['Exit_Price'] > 0].copy()
        if not closed_trades.empty:
            # סינון רווח שנתי (2026)
            current_year = datetime.now().year
            yearly_trades = closed_trades[closed_trades['Exit_Date'].dt.year == current_year]
            yearly_pnl = yearly_trades['PnL'].sum()
            
            # תצוגת סיכום
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric(f"רווח ממומש {current_year}", f"${yearly_pnl:,.2f}")
            with c2:
                st.metric("מספר טריידים שנסגרו", len(yearly_trades))
            with c3:
                win_rate = (len(yearly_trades[yearly_trades['PnL'] > 0]) / len(yearly_trades) * 100) if len(yearly_trades) > 0 else 0
                st.metric("Win Rate", f"{win_rate:.1f}%")

            st.divider()
            st.dataframe(closed_trades.sort_values('Exit_Date', ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("טרם נסגרו טריידים השנה.")

except Exception as e:
    st.error(f"שגיאה: {e}")
