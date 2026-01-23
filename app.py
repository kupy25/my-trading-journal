import streamlit as st
import pandas as pd
import yfinance as yf

# הגדרות האתר
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 יומן מסחר ותחקור - 2026")

# --- הזנת הטריידים מהדו"ח (נתוני אמת) ---
if 'trades' not in st.session_state:
    st.session_state.trades = [
        {"Ticker": "SEDG", "Entry Date": "2026-01-05", "Entry Price": 32.92, "Qty": 174, "Exit Price": 30.45, "P&L": -430.87, "Reason": "תחקיר נדרש"},
        {"Ticker": "PONY", "Entry Date": "2026-01-06", "Entry Price": 17.35, "Qty": 144, "Exit Price": 15.47, "P&L": -270.69, "Reason": "תחקיר נדרש"},
        {"Ticker": "RIVN", "Entry Date": "2026-01-06", "Entry Price": 19.20, "Qty": 286, "Exit Price": 17.40, "P&L": -515.56, "Reason": "תחקיר נדרש"},
        {"Ticker": "RDDT", "Entry Date": "2025-09-20", "Entry Price": 259.60, "Qty": 20, "Exit Price": 218.64, "P&L": -819.18, "Reason": "החזקה ארוכה"},
        {"Ticker": "PLTR", "Entry Date": "2025-11-25", "Entry Price": 164.60, "Qty": 34, "Exit Price": 166.42, "P&L": 61.97, "Reason": "מימוש רווח"},
        {"Ticker": "APA", "Entry Date": "2026-01-20", "Entry Price": 25.87, "Qty": 208, "Exit Price": 26.15, "P&L": 58.28, "Reason": "מימוש מהיר"}
    ]

# סיכום כללי בראש העמוד
st.sidebar.header("💰 סיכום תיק 2026")
total_pnl = sum(t['P&L'] for t in st.session_state.trades)
st.sidebar.metric("רווח/הפסד כולל (YTD)", f"${total_pnl:,.2f}", delta_color="normal")

# ממשק הזנה לטריידים עתידיים
with st.expander("➕ הוספת טרייד חדש"):
    with st.form("new_trade"):
        c1, c2, c3 = st.columns(3)
        with c1:
            t_ticker = st.text_input("Ticker").upper()
            t_entry = st.number_input("מחיר כניסה", min_value=0.0)
        with c2:
            t_qty = st.number_input("כמות", min_value=1)
            t_exit = st.number_input("מחיר יציאה", min_value=0.0)
        with c3:
            t_reason = st.selectbox("סיבת כניסה", ["פריצה", "מעל ממוצע 150", "ספל וידית", "דגל שורי"])
        
        if st.form_submit_button("שמור"):
            pnl = (t_exit - t_entry) * t_qty
            st.session_state.trades.append({
                "Ticker": t_ticker, "Entry Date": "2026-01-23", "Entry Price": t_entry, 
                "Qty": t_qty, "Exit Price": t_exit, "P&L": pnl, "Reason": t_reason
            })
            st.rerun()

# הצגת הטבלה
st.subheader("רשימת טריידים - ינואר 2026")
df = pd.DataFrame(st.session_state.trades)
df['Total Cost'] = df['Entry Price'] * df['Qty']

# עיצוב הטבלה
st.dataframe(df[['Ticker', 'Entry Date', 'Entry Price', 'Qty', 'Total Cost', 'Exit Price', 'P&L', 'Reason']], use_container_width=True)

# תובנות אוטומטיות (תחילת שלב 3)
st.subheader("💡 תובנות לשיפור")
if total_pnl < 0:
    st.warning("שים לב: רוב ההפסדים החודש הגיעו ממניות כמו SEDG ו-RIVN. האם הן היו מעל ממוצע 150 בזמן הקנייה?")
