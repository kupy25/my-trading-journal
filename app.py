import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק ומעקב טריידים - 2026")

# --- הגדרות הון (Portfolio Settings) ---
st.sidebar.header("⚙️ הגדרות חשבון")
initial_capital = st.sidebar.number_input("הון התחלתי ($) - 01.01.2026", value=10000, step=500)

# חיבור ל-Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # טעינת נתונים עם רענון מיידי
    df_trades = conn.read(ttl="0")
    
    if df_trades is not None and not df_trades.empty:
        df_trades.columns = df_trades.columns.str.strip()
        
        # המרת עמודות למספרים בבטחה
        for col in ['Entry_Price', 'Qty', 'Exit_Price', 'PnL']:
            if col in df_trades.columns:
                df_trades[col] = pd.to_numeric(df_trades[col], errors='coerce').fillna(0)

        # חישוב נתוני שוק חיים
        total_realized_pnl = 0
        total_unrealized_pnl = 0
        current_positions_value = 0

        # זיהוי טריידים סגורים (כאלו שיש להם מחיר יציאה)
        closed_trades = df_trades[df_trades['Exit_Price'] > 0]
        total_realized_pnl = closed_trades['PnL'].sum()

        # זיהוי טריידים פתוחים (מחיר יציאה הוא 0 או ריק)
        open_trades = df_trades[df_trades['Exit_Price'] == 0]
        
        st.sidebar.divider()
        st.sidebar.subheader("סטטוס פוזיציות פתוחות")
        
        for index, row in open_trades.iterrows():
            ticker = str(row['Ticker'])
            try:
                stock = yf.Ticker(ticker)
                curr_price = stock.history(period="1d")['Close'].iloc[-1]
                pnl_open = (curr_price - row['Entry_Price']) * row['Qty']
                total_unrealized_pnl += pnl_open
                current_positions_value += (curr_price * row['Qty'])
                st.sidebar.write(f"**{ticker}:** {pnl_open:+.2f}$")
            except:
                st.sidebar.write(f"**{ticker}:** שגיאת נתונים")

        # חישוב שווי תיק כולל
        # שווי תיק = הון התחלתי + רווח ממומש + רווח לא ממומש
        current_equity = initial_capital + total_realized_pnl + total_unrealized_pnl
        
        # תצוגת סיכום ב-Sidebar
        st.sidebar.divider()
        st.sidebar.metric("שווי תיק נוכחי (Live)", f"${current_equity:,.2f}", delta=f"${current_equity - initial_capital:,.2f}")
        st.sidebar.write(f"רווח ממומש: ${total_realized_pnl:,.2f}")
        st.sidebar.write(f"רווח 'על הנייר': ${total_unrealized_pnl:,.2f}")

        # --- תצוגת הטבלה המרכזית ---
        st.subheader("🗂️ יומן טריידים מלא")
        st.dataframe(df_trades, use_container_width=True)

        # --- תחקור Live (ממוצע 150) ---
        st.subheader("🔍 תחקור טכני וכללי ברזל")
        for ticker in df_trades['Ticker'].unique():
            if pd.isna(ticker): continue
            try:
                stock = yf.Ticker(str(ticker))
                hist = stock.history(period="1y")
                curr = hist['Close'].iloc[-1]
                ma150 = hist['Close'].rolling(window=150).mean().iloc[-1]
                
                with st.expander(f"ניתוח עבור {ticker}"):
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        if curr > ma150:
                            st.success(f"✅ מעל 150 MA")
                        else:
