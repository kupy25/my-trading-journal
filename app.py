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
        # ניקוי שמות עמודות
        df_trades.columns = df_trades.columns.str.strip()
        
        # המרת עמודות למספרים
        for col in ['Entry_Price', 'Qty', 'Exit_Price', 'PnL']:
            if col in df_trades.columns:
                df_trades[col] = pd.to_numeric(df_trades[col], errors='coerce').fillna(0)

        # חישוב רווחים ממומשים
        total_realized_pnl = df_trades[df_trades['Exit_Price'] > 0]['PnL'].sum()
        total_unrealized_pnl = 0
        
        # חישוב רווחים "על הנייר" לפוזיציות פתוחות
        open_trades = df_trades[df_trades['Exit_Price'] == 0]
        if not open_trades.empty:
            for index, row in open_trades.iterrows():
                ticker = str(row['Ticker'])
                if ticker and ticker != 'nan' and ticker != "":
                    try:
                        stock = yf.Ticker(ticker)
                        curr_price = stock.history(period="1d")['Close'].iloc[-1]
                        total_unrealized_pnl += (curr_price - row['Entry_Price']) * row['Qty']
                    except:
                        continue

        # שווי תיק כולל ועיצוב
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

        # --- ממשק הוספה ומחשבון ---
        st.header("➕ פעולות ומחשבון")
        col_link, col_calc = st.columns([1, 2])
        
        with col_link:
            st.write("### 📝 הזנת טרייד")
            url = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit"
            st.link_button("פתח גיליון גוגל להזנה", url)
            st.caption("הזן בגיליון ורענן את האתר.")

        with col_calc:
            st.write("### 🧮 מחשבון סיכון (לפני קנייה)")
            with st.expander("בדוק מניה וחשב כמות"):
                calc_ticker = st.text_input("Ticker לבדיקה").upper()
                if calc_ticker:
                    try:
                        s_info = yf.Ticker(calc_ticker)
                        s_hist = s_info.history(period="200d")
                        s_curr = s_hist['Close'].iloc[-1]
                        s_ma150 = s_hist['Close'].rolling(window=150).mean().iloc[-1]
                        
                        if s_curr > s_ma150:
                            st.success(f"{calc_ticker} מעל ממוצע 150 ✅")
                        else:
                            st.error(f"{calc_ticker} מתחת לממוצע 150 ❌")
                        
                        risk = st.number_input("כמה $ לסכן בטרייד?", value=100)
                        stop = st.number_input("מחיר סטופ לוס מתוכנן", value=s_curr*0.95)
                        
                        if s_curr > stop:
                            qty = risk / (s_curr - stop)
                            st.info(f"כמות מומלצת: {int(qty)} מניות")
                            st.write(f"עלות פוזיציה: ${int(qty) * s_curr:,.2f}")
                    except:
                        st.write("הזן טיקר תקין לבדיקה")

        # טבלת טריידים
        st.divider()
        st.subheader("🗂️ יומן טריידים מלא")
        st.dataframe(df_trades, use_container_width=True)

        # תחקור טכני
        st.subheader("🔍 תחקור טכני (Live)")
        unique_tickers = [t for t in df_trades['Ticker'].unique() if pd.notna(t) and t != ""]
        for ticker in unique_tickers:
            try:
                stock = yf.Ticker(str(ticker))
                hist = stock.history(period="1y")
                curr = hist['Close'].iloc[-1]
                ma150 = hist['Close'].rolling(window=150).mean().iloc[-1]
                
                with st.expander(f"ניתוח {ticker}"):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        if curr > ma150:
                            st.success("מגמה: עליה ✅")
                        else:
                            st.error("מגמה: ירידה ❌")
                        st.write(f"מחיר: {curr:.2f}$ | ממוצע 150: {ma150:.2f}$")
                    with c2:
                        st.line_chart(hist['Close'].tail(60))
            except:
                continue

except Exception as e:
    st.error(f"שגיאה במערכת: {e}")
