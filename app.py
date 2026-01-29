import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון (10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key="triple_checked_refresh")

# 2. כתובת הגיליון (חובה להגדיר כאן כדי למנוע שגיאות)
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

# 3. נקודות ייחוס קבועות
CASH_START_REF = 4957.18 
PORTFOLIO_START_VAL = 44302.55 

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

# 4. חיבור וטעינת נתונים
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(spreadsheet=SHEET_URL, ttl="0")
    df.columns = df.columns.str.strip()
    
    # המרת עמודות למספרים
    for col in ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # הפרדה לפתוחות וסגורות
    open_mask = (df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")
    open_trades = df[open_mask].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # --- חישוב עמלות ומזומן אוטומטי ---
    fees_buy = df['Qty'].apply(get_fee).sum()
    fees_sell = closed_trades['Qty'].apply(get_fee).sum()
    total_fees = fees_buy + fees_sell

    invested_now = open_trades['עלות כניסה'].sum()
    realized_pnl = closed_trades['PnL'].sum()
    
    # חישוב היתרה
    current_cash = CASH_START_REF - invested_now - total_fees + realized_pnl

    # --- נתוני לייב ---
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
            p_usd = (val - row['עלות כניסה']) - get_fee(row['Qty'])
            p_pct = ((price - avg_cost) / avg_cost) * 100
            live_list.append({'Ticker': t, 'Qty': row['Qty'], 'Value': val, 'PnL_USD': p_usd, 'PnL_Pct': p_pct})
        live_df = pd.DataFrame(live_list)

    # --- SIDEBAR (ללא RTL ששובר מספרים) ---
    st.sidebar.header("ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${current_cash:,.2f}")
    
    total_val = market_val_total + current_cash
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.write("### שווי תיק כולל")
    st.sidebar.write(f"## ${total_val:,.2f}")
    
    pnl_color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{pnl_color}; font-size: 20px; font-weight: bold;'>{'+' if diff >= 0 else ''}{diff:,.2f}$</p>", unsafe_allow_html=True)
    st.sidebar.write(f"עמלות מצטברות: ${total_fees:,.2f}")

    st.sidebar.divider()
    with st.sidebar.popover("🧮 מחשבון טרייד", use_container_width=True):
        st.subheader("מחשבון גודל פוזיציה")
        c_en = st.number_input("מחיר כניסה $", value=0.0, key="c_en")
        c_st = st.number_input("מחיר סטופ $", value=0.0, key="c_st")
        if c_en > c_st:
            q = int((PORTFOLIO_START_VAL * 0.01) / (c_en - c_st))
            st.success(f"כמות: {q} | עלות: ${q*c_en:,.2f}")

    if not open_trades.empty:
        st.sidebar.subheader("📈 פוזיציות (Live)")
        for _, row in live_df.iterrows():
            c = "#00c853" if row['PnL_USD'] >= 0 else "#ff4b4b"
            st.sidebar.write(f"**{row['Ticker']}:** ${row['Value']:,.2f}")
            st.sidebar.markdown(f"<p style='color:{c}; margin-top:-15px;'>{'+' if row['PnL_USD'] >= 0 else ''}{row['PnL_USD']:,.2f}$ ({row['PnL_Pct']:.2f}%)</p>", unsafe_allow_html=True)

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades.empty:
            st.dataframe(live_df.sort_values('Value', ascending=False), use_container_width=True, hide_index=True)
            st.divider()
            pie_data = pd.concat([live_df[['Ticker', 'Value']], pd.DataFrame([{'Ticker': 'CASH', 'Value': current_cash}])])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Ticker', hole=0.4), use_container_width=True)

    with t2:
        if not closed_trades.empty:
            realized = closed_trades['PnL'].sum()
            st.write(f"### סך רווח ממומש: ${realized:,.2f}")
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL', 'סיבת כניסה', 'סיבת יציאה']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
