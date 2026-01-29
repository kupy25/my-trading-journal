import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון (10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key="clean_stable_refresh")

# 2. נקודות ייחוס
CASH_START = 4957.18 
PORTFOLIO_START_VAL = 44302.55

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

# 3. חיבור לנתונים
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    
    for col in ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # --- חישובים דינמיים ---
    invested_in_open = open_trades['עלות כניסה'].sum()
    fees_open = open_trades['Qty'].apply(get_fee).sum()
    
    # המזומן הפנוי (בלי סימנים הפוכים)
    current_cash = CASH_START - invested_in_open - fees_open

    fees_closed = (closed_trades['Qty'].apply(get_fee).sum() * 2)
    total_fees_display = fees_open + fees_closed

    # --- נתוני לייב ---
    market_val_total = 0
    live_df = pd.DataFrame()

    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum'}).reset_index()
        tickers = list(summary['Ticker'].unique())
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        results = []
        for _, row in summary.iterrows():
            t = row['Ticker']
            price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            val = price * row['Qty']
            market_val_total += val
            avg_cost = row['עלות כניסה'] / row['Qty']
            pnl_usd = (val - row['עלות כניסה']) - get_fee(row['Qty'])
            pnl_pct = ((price - avg_cost) / avg_cost) * 100
            results.append({'Ticker': t, 'Market_Value': val, 'PnL_Net': pnl_usd, 'PnL_Pct': pnl_pct})
        live_df = summary.merge(pd.DataFrame(results), on='Ticker')

    # --- SIDEBAR (ללא שום עיצוב RTL ששובר מספרים) ---
    st.sidebar.header("Management")
    st.sidebar.metric("Available Cash", f"${current_cash:,.2f}")
    
    total_val = market_val_total + current_cash
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.subheader("Total Portfolio Value")
    st.sidebar.markdown(f"## ${total_val:,.2f}")
    
    color = "green" if diff >= 0 else "red"
    st.sidebar.markdown(f"<p style='color:{color}; font-size: 20px;'>Profit/Loss: ${diff:,.2f}</p>", unsafe_allow_html=True)
    
    st.sidebar.write(f"Total Fees: ${total_fees_display:,.2f}")

    # --- מסך ראשי ---
    st.title("Trade Journal")
    t1, t2 = st.tabs(["Open Positions", "Closed Trades"])
    
    with t1:
        if not live_df.empty:
            st.dataframe(live_df, use_container_width=True, hide_index=True)
            st.divider()
            pie_data = pd.concat([live_df[['Ticker', 'Market_Value']], pd.DataFrame([{'Ticker': 'CASH', 'Market_Value': current_cash}])])
            st.plotly_chart(px.pie(pie_data, values='Market_Value', names='Ticker', hole=0.4), use_container_width=True)

    with t2:
        if not closed_trades.empty:
            st.write(f"### Realized P&L: ${closed_trades['PnL'].sum():,.2f}")
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Error: {e}")
