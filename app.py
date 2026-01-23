import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

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

        # הפרדת טריידים
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
                    except: continue

        # חישוב שווי כולל ודלתא
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

        # --- ממשק מרכזי ---
        st.header("➕ פעולות ועדכון")
        st.link_button("📂 פתח גיליון גוגל (אקסל) לעדכון טריידים", "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit")

        tab1, tab2 = st.tabs(["🔓 טריידים פתוחים", "🔒 טריידים סגורים"])
        with tab1:
            st.subheader("פוזיציות פתוחות בניהול")
            st.dataframe(open_trades, use_container_width=True)
            
        with tab2:
            st.subheader("היסטוריית טריידים שמומשו")
            st.dataframe(closed_trades, use_container_width=True)

        # --- תחקור טכני ולוח דוחות ---
        st.divider()
        st.subheader("🔍 תחקור טכני ולוח דוחות")
        for ticker in open_trades['Ticker'].unique():
            if pd.isna(ticker) or ticker == "": continue
            try:
                stock = yf.Ticker(str(ticker))
                hist = stock.history(period="1y")
                if not hist.empty:
                    curr = hist['Close'].iloc[-1]
                    ma150 = hist['Close'].rolling(window=150).mean().iloc[-1]
                    
                    # משיכת תאריך דוח
                    calendar = stock.calendar
                    earnings_date = "אין נתונים"
                    if calendar is not None and 'Earnings Date' in calendar:
                        earnings_date = calendar['Earnings Date'][0].date()

                    with st.expander(f"ניתוח {ticker} | דוח קרוב: {earnings_date}"):
                        c1, c2 = st.columns([1, 2])
                        with c1:
                            if curr > ma150: st.success("מגמה חיובית (מעל 150 MA) ✅")
                            else: st.error("מגמה שלילית (מתחת ל-150 MA) ❌")
                            st.write(f"**מחיר:** {curr:.2f}$")
                            st.write(f"**ממוצע 150:** {ma150:.2f}$")
                            st.write(f"📅 **דוח הבא:** {earnings_date}")
                        with c2:
                            st.line_chart(hist['Close'].tail(60))
            except: continue
    else:
        st.info("הגיליון ריק. הוסף טריידים בגיליון גוגל.")

except Exception as e:
    st.error(f"שגיאה בטעינה: {e}")
