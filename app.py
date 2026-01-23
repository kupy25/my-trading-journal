import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק ומעקב טריידים - 2026")

# --- נתוני יסוד לפי TradeStation ---
st.sidebar.header("⚙️ נתוני חשבון")
initial_value_dec_25 = 44302.55 # שווי ב-31.12.25

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

        # הפרדה מוחלטת בטבלאות
        closed_trades = df_trades[df_trades['Exit_Price'] > 0].copy()
        open_trades = df_trades[df_trades['Exit_Price'] == 0].copy()

        # חישוב שווי שוק נוכחי
        market_value_stocks = 0
        if not open_trades.empty:
            st.sidebar.divider()
            st.sidebar.subheader("פוזיציות פתוחות")
            for index, row in open_trades.iterrows():
                ticker = str(row['Ticker'])
                if ticker and ticker != 'nan':
                    try:
                        stock = yf.Ticker(ticker)
                        curr_price = stock.history(period="1d")['Close'].iloc[-1]
                        pos_val = curr_price * row['Qty']
                        market_value_stocks += pos_val
                        
                        pnl_open = (curr_price - row['Entry_Price']) * row['Qty']
                        st.sidebar.write(f"**{ticker}**: {pos_val:,.2f}$")
                        if pnl_open >= 0:
                            st.sidebar.write(f":green[▲ +{pnl_open:,.2f}$]")
                        else:
                            st.sidebar.write(f":red[▼ {pnl_open:,.2f}$]")
                    except: continue

        # חישוב שווי תיק ודלתא
        total_value_now = market_value_stocks + available_cash
        diff = total_value_now - initial_value_dec_25
        
        # תיקון הבאג הוויזואלי: צבע וחץ ידניים כדי למנוע ירוק בשלילי
        st.sidebar.divider()
        st.sidebar.metric(
            label="שווי תיק כולל (Live)",
            value=f"${total_value_now:,.2f}",
            delta=f"${diff:,.2f}",
            delta_color="normal" # Streamlit יצבע אדום אוטומטית למספר שלילי
        )
        
        # הצגת הפסד ממומש מהדוח שלך
        st.sidebar.write(f"הפסד ממומש (YTD): :red[-1,916.05$]")

        # --- תצוגה מרכזית ---
        st.header("🔄 ניהול פוזיציות")
        
        tab1, tab2 = st.tabs(["🔓 טריידים פתוחים", "🔒 טריידים סגורים"])
        
        with tab1:
            st.subheader("מעקב פוזיציות פעילות")
            st.dataframe(open_trades, use_container_width=True)
            
        with tab2:
            st.subheader("ארכיון עסקאות שמומשו")
            st.dataframe(closed_trades, use_container_width=True)

        # תחקור 150 MA
        st.divider()
        st.subheader("🔍 תחקור טכני 150 MA")
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
