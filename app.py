import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק ומעקב טריידים - 2026")

# --- הגדרות הון (Portfolio Settings) ---
st.sidebar.header("⚙️ הגדרות חשבון")
initial_capital = st.sidebar.number_input("הון התחלתי ($) - 01.01.2026", value=100000, step=1000)

# חיבור ל-Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_trades = conn.read(ttl="0")
    df_trades.columns = df_trades.columns.str.strip()
    
    # חישוב נתונים חיים עבור התיק
    total_realized_pnl = 0
    total_current_value = 0
    
    if not df_trades.empty:
        # המרת עמודות למספרים
        for col in ['Entry_Price', 'Qty', 'Exit_Price', 'PnL']:
            if col in df_trades.columns:
                df_trades[col] = pd.to_numeric(df_trades[col], errors='coerce')

        # הפרדה בין טריידים סגורים לפתוחים
        closed_trades = df_trades[df_trades['Exit_Price'] > 0].copy()
        open_trades = df_trades[(df_trades['Exit_Price'].isna()) | (df_trades['Exit_Price'] == 0)].copy()

        # 1. רווח ממומש (מטריידים סגורים)
        total_realized_pnl = closed_trades['PnL'].sum()

        # 2. שווי נוכחי (מטריידים פתוחים)
        unrealized_pnl = 0
        if not open_trades.empty:
            for index, row in open_trades.iterrows():
                try:
                    ticker = str(row['Ticker'])
                    stock = yf.Ticker(ticker)
                    current_price = stock.history(period="1d")['Close'].iloc[-1]
                    pos_value = current_price * row['Qty']
                    total_current_value += pos_value
                    unrealized_pnl += (current_price - row['Entry_Price']) * row['Qty']
                except:
                    continue

        # --- תצוגת סיכום הון ב-Sidebar ---
        current_equity = initial_capital + total_realized_pnl + unrealized_pnl
        st.sidebar.divider()
        st.sidebar.metric("שווי תיק נוכחי (Live)", f"${current_equity:,.2f}", delta=f"${current_equity - initial_capital:,.2f}")
        st.sidebar.write(f"רווח ממומש: ${total_realized_pnl:,.2f}")
        st.sidebar.write(f"רווח פתוח: ${unrealized_pnl:,.2f}")

        # --- ממשק הוספת מניה חדשה ---
        st.subheader("➕ הוספת טרייד חדש")
        st.info("כדי להוסיף טרייד, מומלץ להזין אותו ישירות בגיליון הגוגל שלך. [לחץ כאן לפתיחת הגיליון](https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit)")
        
        # הצגת הטבלה
        st.subheader("🗂️ יומן טריידים")
        st.dataframe(df_trades, use_container_width=True)

        # --- תחקור אוטומטי ---
        st.subheader("🔍 תחקור Live (ממוצע 150)")
        for ticker in df_trades['Ticker'].unique():
            if pd.isna(ticker): continue
            try:
                stock = yf.Ticker(str(ticker))
                hist = stock.history(period="1y")
                curr = hist['Close'].iloc[-1]
                ma150 = hist['Close'].rolling(window=150).mean().iloc[-1]
                
                with st.expander(f"ניתוח {ticker}"):
                    if curr > ma150:
                        st.success(f"{ticker} מעל ממוצע 150. (מחיר: {curr:.2f}$)")
                    else:
                        st.error(f"{ticker} מתחת לממוצע 150! (מחיר: {curr:.2f}$)")
            except:
                continue
    else:
        st.sidebar.metric("שווי תיק", f"${initial_capital:,.2f}")
        st.info("היומן ריק. הוסף טריידים בגיליון גוגל.")

except Exception as e:
    st.error(f"שגיאה: {e}")
