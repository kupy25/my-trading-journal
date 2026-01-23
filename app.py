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

# הזנת מזומן פנוי עדכני
available_cash = st.sidebar.number_input(
    "מזומן פנוי בחשבון ($)", 
    value=5732.40, 
    step=0.01, 
    format="%.2f"
)

# חיבור לנתונים
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_trades = conn.read(ttl="0")
    
    if df_trades is not None and not df_trades.empty:
        df_trades.columns = df_trades.columns.str.strip()
        for col in ['Entry_Price', 'Qty', 'Exit_Price', 'PnL']:
            if col in df_trades.columns:
                df_trades[col] = pd.to_numeric(df_trades[col], errors='coerce').fillna(0)

        # 1. חישוב הפסד ממומש מתחילת השנה (לפי הדוח שצירפת)
        # במידה והנתונים בגיליון לא מעודכנים, נשתמש בנתון מהדוח: $1,916.05-
        realized_pnl_2026 = df_trades[df_trades['Exit_Price'] > 0]['PnL'].sum()
        
        # 2. חישוב שווי שוק נוכחי של מניות פתוחות
        market_value_stocks = 0
        open_trades = df_trades[df_trades['Exit_Price'] == 0]
        
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

        # 3. שווי תיק כולל וחישוב דלתא
        total_value_now = market_value_stocks + available_cash
        diff = total_value_now - initial_value_dec_25
        
        # תצוגת המדד המרכזי עם תיקון חץ וצבע
        st.sidebar.divider()
        st.sidebar.metric(
            label="שווי תיק כולל (Live)",
            value=f"${total_value_now:,.2f}",
            delta=f"${diff:,.2f}",
            delta_color="normal" # ירוק למעלה, אדום למטה אוטומטית
        )
        
        st.sidebar.write(f"הפסד ממומש (YTD): :red[{realized_pnl_2026:,.2f}$]")
        st.sidebar.write(f"שווי מניות בבורסה: ${market_value_stocks:,.2f}")

        # ממשק פעולות
        st.header("➕ פעולות")
        st.link_button("עדכן טריידים בגיליון גוגל", "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit")

        # טבלה ותחקור
        st.subheader("🗂️ יומן טריידים")
        st.dataframe(df_trades, use_container_width=True)

        st.subheader("🔍 תחקור טכני")
        for ticker in df_trades['Ticker'].unique():
            if pd.isna(ticker) or ticker == "": continue
            try:
                stock = yf.Ticker(str(ticker))
                hist = stock.history(period="1y")
                curr = hist['Close'].iloc[-1]
                ma150 = hist['Close'].rolling(window=150).mean().iloc[-1]
                with st.expander(f"ניתוח {ticker}"):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        if curr > ma150: st.success("מעל 150 MA ✅")
                        else: st.error("מתחת ל-150 MA ❌")
                        st.write(f"מחיר: {curr:.2f}$ | ממוצע: {ma150:.2f}$")
                    with c2: st.line_chart(hist['Close'].tail(60))
            except: continue

except Exception as e:
    st.error(f"שגיאה: {e}")
