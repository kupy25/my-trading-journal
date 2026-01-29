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
st_autorefresh(interval=10000, key=f"auto_cash_engine_{int(time.time())}")

# --- הגדרות ה"עוגן" (נקודת האיפוס של היום) ---
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

    # --- מנוע מזומן אוטומטי ---
    # א. קניות חדשות מהיום והלאה (מפחית מהמזומן)
    new_buys = df[(df['Entry_Date'] > ANCHOR_DATE)]
    cash_out = (new_buys['Qty'] * new_buys['Entry_Price']).sum() + new_buys['Qty'].apply(get_fee).sum()

    # ב. מכירות חדשות מהיום והלאה (מוסיף למזומן)
    new_sells = df[(df['Exit_Date'] > ANCHOR_DATE)]
    cash_in = (new_sells['Qty'] * new_sells['Exit_Price']).sum() - new_sells['Qty'].apply(get_fee).sum()

    # ג. יתרה מחושבת
    calculated_cash = ANCHOR_CASH - cash_out + cash_in

    # --- פוזיציות פתוחות ושווי שוק ---
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull())].copy()
    market_val_total = 0
    live_df = pd.DataFrame()

    if not open_trades.empty:
        reasons = open_trades.groupby('Ticker')['סיבת כניסה'].first().to_dict()
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum'}).reset_index()
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
                'סיבת כניסה': reasons.get(t, "")
            })
        live_df = pd.DataFrame(res)

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון אוטומטי")
    st.sidebar.metric("מזומן מחושב", f"${calculated_cash:,.2f}", 
                     delta=f"{cash_in - cash_out:,.2f}$ מהאיפוס")
    
    total_val = market_val_total + calculated_cash
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.subheader("שווי תיק כולל")
    st.sidebar.title(f"${total_val:,.2f}")
    
    pnl_color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{pnl_color}; font-size: 20px; font-weight: bold;'>{'+' if diff >= 0 else ''}{diff:,.2f}$</p>", unsafe_allow_html=True)

    # מחשבון טרייד
    st.sidebar.divider()
    st.sidebar.subheader("🧮 מחשבון טרייד")
    calc_name = st.sidebar.text_input("שם המניה", placeholder="למשל: NVDA")
    c_entry = st.sidebar.number_input("כניסה $", value=0.0)
    c_stop = st.sidebar.number_input("סטופ $", value=0.0)
    if c_entry > c_stop:
        q = int((total_val * 0.01) / (c_entry - c_stop))
        st.sidebar.success(f"**{calc_name}**\n\nכמות: {q}\n\nעלות: ${q*c_entry:,.2f}")

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    st.link_button("📂 פתח גיליון גוגל שיטס", SHEET_URL)
    
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not live_df.empty:
            def style_pnl(v):
                color = 'green' if v > 0 else 'red'
                return f'color: {color}; font-weight: bold'
            st.dataframe(live_df.style.format({'שווי שוק': '${:,.2f}', 'רווח $': '${:,.2f}', 'רווח %': '{:.2f}%'}).applymap(style_pnl, subset=['רווח $', 'רווח %']), use_container_width=True, hide_index=True)
            
            st.divider()
            pie_data = pd.concat([live_df[['Ticker', 'שווי שוק']].rename(columns={'שווי שוק': 'Value'}), 
                                 pd.DataFrame([{'Ticker': 'מזומן', 'Value': calculated_cash}])])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Ticker', hole=0.4), use_container_width=True)

    with t2:
        closed_trades = df[df['Exit_Price'] > 0].copy()
        if not closed_trades.empty:
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL', 'סיבת יציאה']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
