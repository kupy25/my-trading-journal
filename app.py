import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק ומעקב טריידים - 2026")

# --- נתוני יסוד לפי TradeStation ---
initial_value_dec_25 = 44302.55 

st.sidebar.header("⚙️ נתוני חשבון")
available_cash = st.sidebar.number_input(
    "מזומן פנוי בחשבון ($)", 
    value=5732.40, 
    step=0.01, 
    format="%.2f"
)

conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_trades = conn.read(ttl="0")
    
    if df_trades is not None and not df_trades.empty:
        df_trades.columns = df_trades.columns.str.strip()
        for col in ['Entry_Price', 'Qty', 'Exit_Price', 'PnL']:
            if col in df_trades.columns:
                df_trades[col] = pd.to_numeric(df_trades[col], errors='coerce').fillna(0)

        closed_trades = df_trades[df_trades['Exit_Price'] > 0].copy()
        open_trades = df_trades[df_trades['Exit_Price'] == 0].copy()

        market_value_stocks = 0
        earnings_alerts = []

        if not open_trades.empty:
            st.sidebar.divider()
            st.sidebar.subheader("פוזיציות פתוחות (Live)")
            for index, row in open_trades.iterrows():
                ticker = str(row['Ticker'])
                if ticker and ticker != 'nan' and ticker != "":
                    try:
                        stock = yf.Ticker(ticker)
                        curr_data = stock.history(period="1d")
                        if not curr_data.empty:
                            curr_price = curr_data['Close'].iloc[-1]
                            pos_val = curr_price * row['Qty']
                            market_value_stocks += pos_val
                            pnl_open = (curr_price - row['Entry_Price']) * row['Qty']
                            
                            st.sidebar.write(f"**{ticker}:** {pos_val:,.2f}$")
                            if pnl_open >= 0:
                                st.sidebar.write(f":green[▲ +{pnl_open:,.2f}$]")
                            else:
                                st.sidebar.write(f":red[▼ {pnl_open:,.2f}$]")
                            
                            # בדיקת יום דוחות
                            calendar = stock.calendar
                            if calendar is not None and 'Earnings Date' in calendar:
                                next_earnings = calendar['Earnings Date'][0]
                                days_to_earnings = (next_earnings.date() - datetime.now().date()).days
                                if 0 <= days_to_earnings <= 7:
                                    earnings_alerts.append(f"⚠️ **{ticker}**: דוח בעוד {days_to_earnings} ימים ({next_earnings.date()})")
                    except: continue

        # שווי כולל ודלתא
        total_value_now = market_value_stocks + available_cash
        diff = total_value_now - initial_value_dec_25
        
        st.sidebar.divider()
        st.sidebar.write("### שווי תיק כולל")
        st.sidebar.write(f"## ${total_value_now:,.2f}")
        
        color = "red" if diff < 0 else "green"
        icon = "▼" if diff < 0 else "▲"
        label = "הפסד מתחילת השנה" if diff < 0 else "רווח מתחילת השנה"
        
        st.sidebar.markdown(
            f"<div style='background-color:rgba({('255,0,0,0.1' if diff < 0 else '0,255,0,0.1')}); "
            f"padding:10px; border-radius:10px; border: 1px solid {color};'>"
            f"<p style='color:{color}; margin:0; font-size:14px;'>{label}</p>"
            f"<h3 style='color:{color}; margin:0;'>{icon} ${abs(diff):,.2f}</h3>"
            f"</div>", 
            unsafe_allow_html=True
        )

        # --- תצוגת התראות דוחות ---
        if earnings_alerts:
            st.warning("📅 **שים לב! דוחות מתקרבים:**")
            for alert in earnings_alerts:
                st.write(alert)

        # --- ממשק מרכזי ---
        st.header("➕ פעולות ועדכון")
        st.link_button("📂 פתח גיליון גוגל (אקסל) לעדכון טריידים", "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit")

        tab1, tab2 = st.tabs(["🔓 טריידים פתוחים", "🔒 טריידים סגורים"])
        with tab1:
            st.dataframe(open_trades, use_container_width=True)
        with tab2:
            st.dataframe(closed_trades, use_container_width=True)

        # תחקור 150 MA
        st.divider()
        st.subheader("🔍 תחקור טכני (150 MA)")
        for ticker in open_trades['Ticker'].unique():
            try:
                stock = yf.Ticker(str(ticker))
                hist = stock.history(period="1y")
                curr = hist['Close'].iloc[-1]
                ma150 = hist['Close'].rolling(window=150).mean().iloc[-1]
                with st.expander(f"ניתוח {ticker}"):
                    if curr > ma150: st.success("מגמה חיובית (מעל 150 MA) ✅")
                    else: st.error("מגמה שלילית (מתחת ל-150 MA) ❌")
                    st.line_chart(hist['Close'].tail(60))
            except: continue

except Exception as e:
    st.error(f"שגיאה: {e}")
