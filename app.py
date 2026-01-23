import streamlit as st
import pandas as pd
import yfinance as yf

# הגדרות האתר
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 יומן מסחר ותחקור - 2026")

# אתחול מסד נתונים זמני
if 'trades' not in st.session_state:
    st.session_state.trades = []

# תפריט צד
st.sidebar.header("הגדרות חשבון")
capital = st.sidebar.number_input("סכום השקעה (1.1.2026):", value=100000)

# פונקציה לבדיקת נתוני שוק
def get_stock_info(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        if hist.empty: return None
        current = hist['Close'].iloc[-1]
        ma150 = hist['Close'].rolling(window=150).mean().iloc[-1]
        return {"current": current, "ma150": ma150}
    except:
        return None

# ממשק הזנה
with st.form("trade_form"):
    st.subheader("הכנסת טרייד חדש")
    col1, col2, col3 = st.columns(3)
    with col1:
        t_ticker = st.text_input("מניה (Ticker)").upper()
        t_price = st.number_input("מחיר כניסה", min_value=0.0)
    with col2:
        t_qty = st.number_input("כמות מניות", min_value=1)
        t_stop = st.number_input("סטופ לוס התחלתי", min_value=0.0)
    with col3:
        t_reason = st.selectbox("סיבת כניסה", ["פריצה", "מעל ממוצע 150", "ספל וידית", "דגל שורי", "תחתית כפולה"])
    
    t_notes = st.text_area("הפקת לקחים / הערות")
    
    submitted = st.form_submit_button("שמור טרייד")
    if submitted and t_ticker:
        info = get_stock_info(t_ticker)
        new_trade = {
            "Ticker": t_ticker,
            "Entry Price": t_price,
            "Qty": t_qty,
            "Total Cost": t_price * t_qty,
            "Stop Loss": t_stop,
            "Reason": t_reason,
            "Current Price": info['current'] if info else 0,
            "Above MA150": "✅" if info and info['current'] > info['ma150'] else "❌",
            "Notes": t_notes
        }
        st.session_state.trades.append(new_trade)
        st.success(f"הטרייד על {t_ticker} נשמר!")

# הצגת טבלת הטריידים
if st.session_state.trades:
    df = pd.DataFrame(st.session_state.trades)
    st.dataframe(df, use_container_width=True)
else:
    st.info("היומן ריק. הכנס את הטרייד הראשון שלך מתחילת השנה.")
