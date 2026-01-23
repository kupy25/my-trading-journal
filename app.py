import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק ומעקב טריידים - 2026")

# --- הגדרות הון ---
st.sidebar.header("⚙️ הגדרות חשבון")
initial_capital = st.sidebar.number_input("הון התחלתי ($) - 01.01.2026", value=10000, step=500)

# חיבור ל-Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_trades = conn.read(ttl="0")
    
    if df_trades is not None:
        df_trades.columns = df_trades.columns.str.strip()
        
        for col in ['Entry_Price', 'Qty', 'Exit_Price', 'PnL']:
            if col in df_trades.columns:
                df_trades[col] = pd.to_numeric(df_trades[col], errors='coerce').fillna(0)

        # חישוב רווחים
        total_realized_pnl = df_trades[df_trades['Exit_Price'] > 0]['PnL'].sum()
        total_unrealized_pnl = 0
        
        # חישוב פוזיציות פתוחות
        open_trades = df_trades[df_trades['Exit_Price'] == 0]
        for index, row in open_trades.iterrows():
            try:
                ticker = str(row['Ticker'])
                if ticker and ticker != 'nan':
                    stock = yf.Ticker(ticker)
                    curr_price = stock.history(period="1d")['Close'].iloc[-1]
                    total_unrealized_pnl += (curr_price - row['Entry_Price']) * row['Qty']
            except:
                continue

        # שווי תיק כולל ועיצוב צבעים
        current_equity = initial_capital + total_realized_pnl + total_unrealized_pnl
        diff = current_equity - initial_capital
        
        st.sidebar.divider()
        st.sidebar.metric(
            label="שווי תיק נוכחי (Live)", 
            value=f"${current_equity:,.2f}", 
            delta=f"${diff:,.2f}",
            delta_color="normal" if diff >= 0 else "inverse"
        )
        
        st.sidebar.write(f"רווח ממומש: ${total_realized_pnl:,.2f}")
        st.sidebar.write(f"רווח 'על הנייר': ${total_unrealized_pnl:,.2f}")

        # --- ממשק הוספת טרייד חדש ---
        st.header("➕ הוספת טרייד חדש")
        col_link, col_manual = st.columns([1, 2])
        
        with col_link:
            st.write("### דרך א': הזנה בגיליון")
            st.link_button("פתח גיליון גוגל להזנה", "
