import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 יומן מסחר ותחקור - 2026")

# חיבור ל-Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# טעינת נתונים מהגיליון
def load_data():
    return conn.read(ttl="1m")

df_trades = load_data()

# סיכום בתפריט צד
st.sidebar.header("💰 סיכום תיק 2026")
if not df_trades.empty and 'PnL' in df_trades.columns:
    total_pnl = df_trades['PnL'].sum()
    st.sidebar.metric("רווח/הפסד כולל (YTD)", f"${total_pnl:,.2f}")

# פונקציה לבדיקת נתוני שוק (ממוצע 150 ודוחות)
def get_stock_analysis(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        current_price = hist['Close'].iloc[-1]
        ma150 = hist['Close'].rolling(window=150).mean().iloc[-1]
        
        # בדיקת דוחות (Earnings)
        calendar = stock.calendar
        next_earnings = calendar.get('Earnings Date', [None])[0]
        
        return current_price, ma150, next_earnings
    except:
        return None, None, None

# ממשק הזנה
with st.expander("➕ הוספת טרייד חדש (נשמר בגיליון)"):
    with st.form("trade_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            t_ticker = st.text_input("Ticker").upper()
            t_entry_date = st.date_input("תאריך כניסה")
            t_entry_price = st.number_input("מחיר כניסה", min_value=0.0, step=0.01)
        with col2:
            t_qty = st.number_input("כמות", min_value=1, step=1)
            t_exit_price = st.number_input("מחיר יציאה", min_value=0.0, step=0.01)
        with col3:
            t_reason = st.selectbox("סיבת כניסה", ["פריצה", "מעל ממוצע 150", "ספל וידית", "דגל שורי", "תחתית כפולה"])
            t_notes = st.text_area("הערות ותחקיר")

        if st.form_submit_button("שמור טרייד"):
            pnl = (t_exit_price - t_entry_price) * t_qty
            new_row = pd.DataFrame([{
                "Ticker": t_ticker, "Entry_Date": str(t_entry_date), "Entry_Price": t_entry_price,
                "Qty": t_qty, "Exit_Price": t_exit_price, "PnL": pnl, "Reason": t_reason, "Notes": t_notes
            }])
            updated_df = pd.concat([df_trades, new_row], ignore_index=True)
            conn.update(data=updated_df)
            st.success(f"הטרייד על {t_ticker} נשמר בגיליון גוגל!")
            st.rerun()

# הצגת הטבלה עם ניתוח חי
if not df_trades.empty:
    st.subheader("יומן טריידים מנוהל")
    # הוספת חישוב עלות כוללת לתצוגה
    display_df = df_trades.copy()
    display_df['Total_Cost'] = display_df['Entry_Price'] * display_df['Qty']
    st.dataframe(display_df, use_container_width=True)

    # שלב 3: רשימת מעקב ובדיקת כללי ברזל
    st.subheader("🔍 תחקור אוטומטי (כללי ברזל)")
    for ticker in df_trades['Ticker'].unique():
        curr, ma, earnings = get_stock_analysis(ticker)
        if curr and ma:
            status = "✅ מעל 150 MA" if curr > ma else "❌ מתחת ל-150 MA"
            earning_str = f"| דוח קרוב: {earnings.date()}" if earnings else ""
            st.write(f"**{ticker}**: מחיר {curr:.2f}$ | {status} {earning_str}")
