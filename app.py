import streamlit as st
import pandas as pd
import yfinance as yf

# הגדרות האתר
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 יומן מסחר ותחקור - 2026")

# --- נתונים ראשוניים מתחילת השנה (01.01.2026) ---
# הערה: כאן נכניס את הטריידים שלך ברגע שתשלח לי אותם
if 'trades' not in st.session_state:
    st.session_state.trades = [] 

# תפריט צד
st.sidebar.header("הגדרות חשבון")
capital = st.sidebar.number_input("סכום השקעה התחלתי (1.1.2026):", value=100000)

# פונקציה לבדיקת ממוצע 150
def check_ma150(ticker):
    try:
        data = yf.Ticker(ticker).history(period="1y")
        ma150 = data['Close'].rolling(window=150).mean().iloc[-1]
        current = data['Close'].iloc[-1]
        return current, ma150
    except:
        return None, None

# ממשק הזנה
with st.form("trade_form"):
    st.subheader("הכנסת טרייד חדש / רטרואקטיבי")
    col1, col2 = st.columns(2)
    with col1:
        t_ticker = st.text_input("מניה (Ticker)").upper()
        t_price = st.number_input("מחיר כניסה", min_value=0.0)
    with col2:
        t_qty = st.number_input("כמות מניות", min_value=1)
        t_reason = st.selectbox("סיבת כניסה", ["פריצה", "מעל ממוצע 150", "ספל וידית", "דגל שורי", "אחר"])
    
    submitted = st.form_submit_button("הוסף ליומן")
    if submitted and t_ticker:
        curr, ma = check_ma150(t_ticker)
        st.session_state.trades.append({
            "Ticker": t_ticker, "Price": t_price, "Qty": t_qty, "Reason": t_reason, "Current": curr, "MA150": ma
        })
        st.success(f"הטרייד על {t_ticker} נוסף בהצלחה!")

# הצגת הטריידים
if st.session_state.trades:
    df = pd.DataFrame(st.session_state.trades)
    st.table(df)
