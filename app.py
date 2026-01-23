import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק ומעקב טריידים - 2026")

# --- נתוני יסוד לפי TradeStation ---
initial_value_dec_25 = 44302.55 
st.sidebar.header("⚙️ נתוני חשבון")
available_cash = st.sidebar.number_input("מזומן פנוי בחשבון ($)", value=5732.40, step=0.01, format="%.2f")

conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_trades = conn.read(ttl="0")
    if df_trades is not None and not df_trades.empty:
        df_trades.columns = df_trades.columns.str.strip()
        for col in ['Entry_Price', 'Qty', 'Exit_Price', 'PnL']:
            if col in df_trades.columns:
                df_trades[col] = pd.to_numeric(df_trades[col], errors='coerce').fillna(0)

        # הפרדה מוחלטת
        closed_trades = df_trades[df_trades['Exit_Price'] > 0].copy()
        open_trades = df_trades[df_trades['Exit_Price'] == 0].copy()

        market_value_stocks = 0
        if not open_trades.empty:
            st.sidebar.divider()
            st.sidebar.subheader("פוזיציות פתוחות (Live)")
            for _, row in open_trades.iterrows():
                ticker = str(row['Ticker']).strip()
                if ticker and ticker.lower() != 'nan':
                    try:
                        stock = yf.Ticker(ticker)
                        curr_p = stock.history(period="1d")['Close'].iloc[-1]
                        market_value_stocks += (curr_p * row['Qty'])
                        pnl_open = (curr_p - row['Entry_Price']) * row['Qty']
                        st.sidebar.write(f"**{ticker}:** {curr_p * row['Qty']:,.2f}$")
                        st.sidebar.write(f":green[▲ +{pnl_open:,.2f}$]" if pnl_open >= 0 else f":red[▼ {pnl_open:,.2f}$]")
                    except: continue

        # חישוב שווי כולל ודלתא
        total_value_now = market_value_stocks + available_cash
        diff = total_value_now - initial_value_dec_25

        # --- תיקון ויזואלי סופי ב-Sidebar ---
        st.sidebar.divider()
        st.sidebar.write("### שווי תיק כולל")
        st.sidebar.write(f"## ${total_value_now:,.2f}")
        
        # בניית תיבת "רווח/הפסד מתחילת השנה"
        color = "#ff4b4b" if diff < 0 else "#00c853" # אדום או ירוק
        icon = "▼" if diff < 0 else "▲"
        label = "הפסד מתחילת השנה" if diff < 0 else "רווח מתחילת השנה"
        
        st.sidebar.markdown(
            f"""<div style="border: 1px solid {color}; border-radius: 5px; padding: 10px; background-color: rgba(0,0,0,0.05);">
                <p style="margin: 0; font-size: 14px; color: gray;">{label}</p>
                <h3 style="margin: 0; color: {color};">{icon} ${abs(diff):,.2f}</h3>
            </div>""", unsafe_allow_html=True
        )

        # --- תצוגה מרכזית ---
        st.header("🔄 ניהול פוזיציות")
        st.link_button("📂 פתח גיליון גוגל לעדכון", "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit")

        tab1, tab2 = st.tabs(["🔓 טריידים פתוחים", "🔒 טריידים סגורים"])
        
        with tab1:
            st.subheader("פוזיציות פעילות")
            st.dataframe(open_trades, use_container_width=True)
            st.divider()
            st.subheader("🔍 תחקור טכני ולוח דוחות (פוזיציות פתוחות)")
            
            # סריקה יסודית של כל הטיקרים בטבלת הפתוחים
            unique_open_tickers = open_trades['Ticker'].dropna().unique()
            for ticker in unique_open_tickers:
                ticker = str(ticker).strip()
                if not ticker or ticker.lower() == 'nan': continue
                try:
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period="1y")
                    if not hist.empty:
                        curr = hist['Close'].iloc[-1]
                        ma150 = hist['Close'].rolling(window=150).mean().iloc[-1]
                        cal = stock.calendar
                        e_date = cal['Earnings Date'][0].date() if (cal is not None and 'Earnings Date' in cal) else "לא ידוע"
                        
                        with st.expander(f"ניתוח {ticker} | דוח: {e_date}"):
                            c1, c2 = st.columns([1, 2])
                            with c1:
                                if curr > ma150: st.success("מגמה חיובית (מעל 150 MA) ✅")
                                else: st.error("מגמה שלילית (מתחת ל-150 MA) ❌")
                                st.write(f"**מחיר:** {curr:.2f}$ | **150 MA:** {ma150:.2f}$")
                                st.write(f"📅 **דוח:** {e_date}")
                            with c2: st.line_chart(hist['Close'].tail(60))
                except: continue

        with tab2:
            st.subheader("היסטוריית עסקאות")
            st.dataframe(closed_trades, use_container_width=True)
            st.info("בטבלה זו מוצגים טריידים שהסתיימו. תחקור טכני חי אינו זמין עבורם.")

except Exception as e:
    st.error(f"שגיאה: {e}")
