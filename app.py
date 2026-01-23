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
    
    if df_trades is not None and not df_trades.empty:
        df_trades.columns = df_trades.columns.str.strip()
        
        for col in ['Entry_Price', 'Qty', 'Exit_Price', 'PnL']:
            if col in df_trades.columns:
                df_trades[col] = pd.to_numeric(df_trades[col], errors='coerce').fillna(0)

        total_realized_pnl = df_trades[df_trades['Exit_Price'] > 0]['PnL'].sum()
        total_unrealized_pnl = 0
        
        # חישוב רווח לא ממומש (פוזיציות פתוחות)
        open_trades = df_trades[df_trades['Exit_Price'] == 0]
        for index, row in open_trades.iterrows():
            try:
                ticker = str(row['Ticker'])
                stock = yf.Ticker(ticker)
                curr_price = stock.history(period="1d")['Close'].iloc[-1]
                total_unrealized_pnl += (curr_price - row['Entry_Price']) * row['Qty']
            except:
                continue

        # שווי תיק כולל
        current_equity = initial_capital + total_realized_pnl + total_unrealized_pnl
        diff = current_equity - initial_capital
        
        # הגדרת צבע וחץ לפי ביצועים
        delta_color = "normal" if diff >= 0 else "inverse"
        
        st.sidebar.divider()
        st.sidebar.metric(
            label="שווי תיק נוכחי (Live)", 
            value=f"${current_equity:,.2f}", 
            delta=f"${diff:,.2f}",
            delta_color=delta_color
        )
        
        st.sidebar.write(f"רווח ממומש: ${total_realized_pnl:,.2f}")
        st.sidebar.write(f"רווח 'על הנייר': ${total_unrealized_pnl:,.2f}")

        # הצגת הטבלה
        st.subheader("🗂️ יומן טריידים מלא")
        st.dataframe(df_trades, use_container_width=True)

        # תחקור Live
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
                            st.success(f"✅ מעל 150 MA (מגמת עלייה)")
                        else:
                            st.error(f"❌ מתחת ל-150 MA (מגמת ירידה)")
                        st.write(f"מחיר: {curr:.2f}$ | ממוצע: {ma150:.2f}$")
                    with col2:
                        st.line_chart(hist['Close'].tail(60))
            except:
                continue
    else:
        st.sidebar.metric("שווי תיק", f"${initial_capital:,.2f}")
        st.info("היומן ריק בגיליון גוגל.")

except Exception as e:
    st.error(f"שגיאה במערכת: {e}")
