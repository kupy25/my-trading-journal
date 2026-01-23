import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק ומעקב טריידים - 2026")

# --- הגדרות הון ומזומן (Sidebar) ---
st.sidebar.header("⚙️ ניהול מזומן והון")
initial_total_value = 44302.55 # השווי ב-31.12.2025 לפי Tradestation

# שדה להזנת מזומן פנוי בתיק
available_cash = st.sidebar.number_input("מזומן פנוי בחשבון ($)", value=5000.0, step=100.0)

# חיבור ל-Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_trades = conn.read(ttl="0")
    
    if df_trades is not None:
        df_trades.columns = df_trades.columns.str.strip()
        for col in ['Entry_Price', 'Qty', 'Exit_Price', 'PnL']:
            if col in df_trades.columns:
                df_trades[col] = pd.to_numeric(df_trades[col], errors='coerce').fillna(0)

        # חישוב שווי המניות הפתוחות "על הנייר"
        stock_value_on_paper = 0
        total_realized_pnl = df_trades[df_trades['Exit_Price'] > 0]['PnL'].sum()
        
        open_trades = df_trades[df_trades['Exit_Price'] == 0]
        if not open_trades.empty:
            st.sidebar.divider()
            st.sidebar.subheader("שווי פוזיציות פתוחות")
            for index, row in open_trades.iterrows():
                ticker = str(row['Ticker'])
                if ticker and ticker != 'nan' and ticker != "":
                    try:
                        stock = yf.Ticker(ticker)
                        curr_price = stock.history(period="1d")['Close'].iloc[-1]
                        current_pos_value = curr_price * row['Qty']
                        stock_value_on_paper += current_pos_value
                        
                        pnl_open = (curr_price - row['Entry_Price']) * row['Qty']
                        color = "green" if pnl_open >= 0 else "red"
                        st.sidebar.markdown(f"**{ticker}:** {current_pos_value:,.2f}$ (<span style='color:{color}'>{pnl_open:+.2f}$</span>)", unsafe_allow_html=True)
                    except:
                        continue

        # --- חישוב שווי תיק כולל ---
        total_portfolio_value = stock_value_on_paper + available_cash
        diff_from_start = total_portfolio_value - initial_total_value
        
        st.sidebar.divider()
        # תצוגת שווי כולל (מניות + מזומן)
        st.sidebar.metric(
            label="שווי תיק כולל (Cash + Stocks)", 
            value=f"${total_portfolio_value:,.2f}", 
            delta=f"${diff_from_start:,.2f}",
            delta_color="normal" if diff_from_start >= 0 else "inverse"
        )
        
        # פירוט נוסף ב-Sidebar
        st.sidebar.write(f"📈 שווי מניות על הנייר: ${stock_value_on_paper:,.2f}")
        st.sidebar.write(f"💵 מזומן פנוי: ${available_cash:,.2f}")

        # --- ממשק מרכזי ---
        st.header("➕ פעולות")
        url = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit"
        st.link_button("עדכן טריידים בגיליון גוגל", url)

        # טבלת טריידים
        st.subheader("🗂️ יומן טריידים")
        st.dataframe(df_trades, use_container_width=True)

        # תחקור טכני
        st.subheader("🔍 תחקור טכני Live")
        unique_tickers = [t for t in df_trades['Ticker'].unique() if pd.notna(t) and t != ""]
        for ticker in unique_tickers:
            try:
                stock = yf.Ticker(str(ticker))
                hist = stock.history(period
