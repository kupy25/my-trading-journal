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
initial_value_dec_25 = 44302.55

conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # 1. קריאת נתונים (ללא ניקוי כותרות אגרסיבי כדי לא לפספס את עמודה L)
    df = conn.read(ttl="0")
    
    # 2. שליפת מזומן בסיס מעמודה L (Cash_Base)
    base_cash = 0.0
    if 'Cash_Base' in df.columns:
        # לוקח את הערך המספרי הראשון בעמודה L
        val = pd.to_numeric(df['Cash_Base'], errors='coerce').dropna()
        if not val.empty:
            base_cash = float(val.iloc[0])

    # 3. המרת עמודות למספרים לחישובים (שימוש בשמות המדויקים מהגיליון שלך)
    cols_to_fix = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'עלות יציאה', 'PnL']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 4. הפרדה לפתוחים וסגורים
    # פתוח = מחיר יציאה הוא 0 ויש שם למניה
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull())].copy()
    # סגור = מחיר יציאה גדול מ-0
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # --- חישוב מזומן דינמי אוטומטי (הבקשה שלך) ---
    # א. סכום הכסף שמושקע כרגע (יוצא מהמזומן)
    total_invested = open_trades['עלות כניסה'].sum()
    
    # ב. סכום הכסף שחזר ממכירות (נכנס למזומן)
    total_returned = closed_trades['עלות יציאה'].sum()
    
    # ג. היתרה הנוכחית: בסיס פחות קניות פלוס מכירות
    current_cash = base_cash - total_invested + total_returned

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ נתוני חשבון")
    
    # תצוגת המזומן המחושב
    st.sidebar.metric("מזומן פנוי (דינמי)", f"${current_cash:,.2f}")
    st.sidebar.caption(f"מזומן בסיס בגיליון: ${base_cash:,.2f}")
    
    if base_cash == 0:
        st.sidebar.error("⚠️ לא נמצא בסיס מזומן בעמודה L. וודא שהכותרת היא Cash_Base.")

    # מחשבון גודל פוזיציה
    st.sidebar.divider()
    st.sidebar.subheader("🧮 מחשבון טרייד")
    calc_t = st.sidebar.text_input("טיקר", "").upper()
    e_p = st.sidebar.number_input("כניסה $", value=0.0)
    s_p = st.sidebar.number_input("סטופ $", value=0.0)
    
    if calc_t and e_p > s_p:
        risk_per_trade = initial_value_dec_25 * 0.01 
        qty = min(int(risk_per_trade / (e_p - s_p)), int(current_cash / e_p))
        if qty > 0:
            st.sidebar.success(f"כמות: {qty} | עלות: ${qty*e_p:,.2f}")
        else: st.sidebar.warning("אין מספיק מזומן פנוי")

    # --- פוזיציות לייב ---
    st.sidebar.divider()
    st.sidebar.subheader("📈 פוזיציות (Live)")
    tickers = open_trades['Ticker'].dropna().unique()
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
        except: st.sidebar.write("ממתין לנתוני שוק...")

    # שווי תיק כולל
    total_portfolio = market_val_total + current_cash
    st.sidebar.divider()
    st.sidebar.metric("שווי תיק כולל", f"${total_portfolio:,.2f}", 
                      delta=f"${total_portfolio - initial_value_dec_25:,.2f}")

    # --- תצוגה מרכזית ---
    st.link_button("📂 פתח גיליון לעדכון טריידים", SHEET_URL, use_container_width=True, type="primary")
    
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    with t1:
        st.dataframe(open_trades[['Ticker', 'Entry_Date', 'Qty', 'Entry_Price', 'עלות כניסה', 'סיבת כניסה']], use_container_width=True)
    with t2:
        st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'Entry_Price', 'עלות כניסה', 'Exit_Price', 'עלות יציאה', 'PnL', 'סיבת יציאה']], use_container_width=True)

except Exception as e:
    st.error(f"שגיאה במערכת: {e}")
