import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
import plotly.express as px

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק ומעקב טריידים - 2026")

# הקישור לגיליון שלך
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

# --- נתוני יסוד קבועים (Hardcoded) ---
CASH_START = 4957.18  # המזומן ההתחלתי שלך כפי שמופיע בגיליון
initial_portfolio_value = 44302.55 # שווי התיק ב-31.12.25

conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # 1. קריאת נתונים מהגיליון הראשי
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()

    # 2. המרת עמודות למספרים לחישובים (שימוש בשמות המדויקים מהגיליון שלך)
    cols_to_fix = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'עלות יציאה', 'PnL']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 3. הפרדה לפתוחים וסגורים
    # פתוח = מחיר יציאה הוא 0 ויש שם למניה
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    # סגור = מחיר יציאה גדול מ-0
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # --- חישוב מזומן דינמי אוטומטי ---
    # א. כסף שמושקע כרגע במניות פתוחות (יוצא מהמזומן)
    total_invested_now = open_trades['עלות כניסה'].sum()
    
    # ב. כסף שחזר ממכירות שבוצעו (נכנס חזרה למזומן)
    # הערה: אנחנו מחשבים רק טריידים שנסגרו *אחרי* שהגדרנו את ה-4957 כבסיס
    # אם ה-4957 כבר כולל מכירות עבר, נחשב רק טריידים חדשים או את הדלתא.
    # לדיוק מקסימלי, נחשב את כל תזרים המזומנים מהטריידים בגיליון:
    total_returned_from_sales = closed_trades['עלות יציאה'].sum()
    
    # ג. היתרה הנוכחית
    current_cash = CASH_START - total_invested_now + total_returned_from_sales

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ נתוני חשבון")
    
    # תצוגת המזומן הדינמי המעודכן
    st.sidebar.metric("מזומן פנוי (דינמי)", f"${current_cash:,.2f}")
    st.sidebar.caption(f"בסיס מזומן קבוע: ${CASH_START:,.2f}")
    st.sidebar.write(f"💰 מושקע כרגע: ${total_invested_now:,.2f}")

    # מחשבון גודל פוזיציה
    st.sidebar.divider()
    st.sidebar.subheader("🧮 מחשבון טרייד")
    calc_t = st.sidebar.text_input("טיקר לבדיקה", "").upper()
    e_p = st.sidebar.number_input("מחיר כניסה $", value=0.0)
    s_p = st.sidebar.number_input("סטופ לוס $", value=0.0)
    
    if calc_t and e_p > s_p:
        risk_per_trade = initial_portfolio_value * 0.01 # סיכון של 1% מהתיק
        qty = min(int(risk_per_trade / (e_p - s_p)), int(current_cash / e_p))
        if qty > 0:
            st.sidebar.success(f"כמות: {qty} | עלות: ${qty*e_p:,.2f}")
        else: st.sidebar.warning("אין מספיק מזומן פנוי לטרייד")

    # --- פוזיציות לייב ב-Sidebar ---
    st.sidebar.divider()
    st.sidebar.subheader("📈 פוזיציות (Live)")
    tickers = open_trades['Ticker'].unique()
    market_val_total = 0
    
    if len(tickers) > 0:
        try:
            data = yf.download(list(tickers), period="1d", progress=False)['Close']
            for t in tickers:
                curr = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
                t_rows = open_trades[open_trades['Ticker'] == t]
                val = (curr * t_rows['Qty']).sum()
                pnl = ((curr - t_rows['Entry_Price']) * t_rows['Qty']).sum()
                market_val_total += val
                
                st.sidebar.write(f"**{t}:** ${val:,.2f}")
                color = "#00c853" if pnl >= 0 else "#ff4b4b"
                st.sidebar.markdown(f"<p style='color:{color}; margin-top:-15px;'>{'+' if pnl >= 0 else ''}{pnl:,.2f}$</p>", unsafe_allow_html=True)
        except: st.sidebar.write("טוען נתונים...")

    # שווי תיק כולל
    total_portfolio = market_val_total + current_cash
    st.sidebar.divider()
    st.sidebar.metric("שווי תיק כולל", f"${total_portfolio:,.2f}", 
                      delta=f"${total_portfolio - initial_portfolio_value:,.2f}")

    # --- תצוגה מרכזית ---
    st.link_button("📂 פתח גיליון לעדכון טריידים", SHEET_URL, use_container_width=True, type="primary")
    
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    with t1:
        st.dataframe(open_trades[['Ticker', 'Entry_Date', 'Qty', 'Entry_Price', 'עלות כניסה', 'סיבת כניסה']], use_container_width=True)
    with t2:
        st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'Entry_Price', 'עלות כניסה', 'Exit_Price', 'עלות יציאה', 'PnL', 'סיבת יציאה']], use_container_width=True)

except Exception as e:
    st.error(f"שגיאה במערכת: {e}")
