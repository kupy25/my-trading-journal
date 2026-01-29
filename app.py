import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון אוטומטי (10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key="stable_final_v1")

# 2. נתוני בסיס וכתובת הגיליון
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"
CASH_START_REF = 4957.18 
PORTFOLIO_START_VAL = 44302.55 

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

# 3. חיבור לנתונים
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(spreadsheet=SHEET_URL, ttl="0")
    df.columns = df.columns.str.strip()
    
    # המרת עמודות למספרים
    for col in ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # הפרדה לפתוחות וסגורות
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # --- חישובים אוטומטיים ---
    fees_total = df['Qty'].apply(get_fee).sum() + closed_trades['Qty'].apply(get_fee).sum()
    invested_now = open_trades['עלות כניסה'].sum()
    realized_pnl = closed_trades['PnL'].sum()
    current_cash = CASH_START_REF - invested_now - fees_total + realized_pnl

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

    # --- SIDEBAR (תצוגה נקייה ללא RTL) ---
    st.sidebar.header("Account Management")
    st.sidebar.metric("Available Cash", f"${current_cash:,.2f}")
    
    total_val = market_val_total + current_cash
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.subheader("Total Value")
    st.sidebar.title(f"${total_val:,.2f}")
    
    pnl_color = "green" if diff >= 0 else "red"
    st.sidebar.markdown(f"<p style='color:{pnl_color}; font-size: 20px;'>P/L: ${diff:,.2f}</p>", unsafe_allow_html=True)
    st.sidebar.write(f"Total Fees: ${fees_total:,.2f}")

    if not open_trades.empty:
        st.sidebar.divider()
        st.sidebar.subheader("Live Positions")
        for _, row in live_df.iterrows():
            c = "green" if row['PnL_USD'] >= 0 else "red"
            st.sidebar.write(f"**{row['Ticker']}**: ${row['Value']:,.2f} ({row['PnL_Pct']:.2f}%)")

    # --- מסך ראשי ---
    st.title("Trade Journal")
    t1, t2 = st.tabs(["Open Positions", "Closed Trades"])
    
    with t1:
        if not open_trades.empty:
            st.dataframe(live_df, use_container_width=True, hide_index=True)
            st.divider()
            pie_data = pd.concat([live_df[['Ticker', 'Value']], pd.DataFrame([{'Ticker': 'CASH', 'Value': current_cash}])])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Ticker', hole=0.4), use_container_width=True)

    with t2:
        if not closed_trades.empty:
            st.write(f"### Realized P&L: ${closed_trades['PnL'].sum():,.2f}")
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL', 'סיבת כניסה', 'סיבת יציאה']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Error: {e}")
