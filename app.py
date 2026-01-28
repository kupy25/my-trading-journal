import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
import plotly.express as px

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק ומעקב טריידים - 2026")

SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"
initial_value_dec_25 = 44302.55

conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # 1. קריאת נתונים וניקוי כותרות (הסרת רווחים וסימנים)
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip().str.replace(' ', '_').str.replace('__', '_')

    # 2. שליפת מזומן בסיס (מחפש את העמודה Cash_Base או כל עמודה עם "מזומן")
    base_cash = 0.0
    cash_col = [c for c in df.columns if 'Cash' in c or 'מזומן' in c]
    if cash_col:
        valid_vals = pd.to_numeric(df[cash_col[0]], errors='coerce').dropna()
        if not valid_vals.empty:
            base_cash = float(valid_vals.iloc[0])

    # 3. המרת עמודות למספרים לחישובים
    numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות_כניסה', 'עלות_יציאה', 'PnL']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # הפרדה לפתוחים וסגורים
    open_trades = df[df['Exit_Price'] == 0].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # --- חישוב מזומן דינמי אוטומטי ---
    # קניות: סכום עלות הכניסה של כל מה שפתוח
    total_spent_open = open_trades['עלות_כניסה'].sum()
    # מכירות: סכום עלות היציאה של כל מה שנסגר (הכסף שחזר לחשבון)
    total_returned_closed = closed_trades['עלות_יציאה'].sum()
    
    # הנוסחה שביקשת: בסיס פחות קניות פלוס מכירות
    current_cash = base_cash - total_spent_open + total_returned_closed

    # --- SIDEBAR: תצוגת נתונים ---
    st.sidebar.header("⚙️ נתוני חשבון")
    
    # הצגת המזומן הדינמי עם הסבר
    st.sidebar.metric("מזומן פנוי (דינמי)", f"${current_cash:,.2f}")
    st.sidebar.caption(f"בסיס בגיליון: ${base_cash:,.2f}")
    
    if base_cash == 0:
        st.sidebar.error("⚠️ שים לב: מזומן הבסיס נקרא כ-0. וודא ששם העמודה בגיליון הוא Cash_Base")

    # מחשבון גודל פוזיציה
    st.sidebar.divider()
    st.sidebar.subheader("🧮 מחשבון טרייד")
    calc_t = st.sidebar.text_input("טיקר", "").upper()
    e_p = st.sidebar.number_input("כניסה $", value=0.0)
    s_p = st.sidebar.number_input("סטופ $", value=0.0)
    
    if calc_t and e_p > s_p:
        risk_amt = initial_value_dec_25 * 0.01 # ברירת מחדל 1% סיכון
        qty = min(int(risk_amt / (e_p - s_p)), int(current_cash / e_p))
        st.sidebar.success(f"כמות: {qty} | עלות: ${qty*e_p:,.2f}")

    # --- פוזיציות לייב ---
    st.sidebar.divider()
    st.sidebar.subheader("📈 פוזיציות (Live)")
    tickers = open_trades['Ticker'].unique()
    market_val = 0
    if len(tickers) > 0:
        data = yf.download(list(tickers), period="1d", progress=False)['Close']
        for t in tickers:
            curr = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            row = open_trades[open_trades['Ticker'] == t].iloc[0]
            val = curr * row['Qty']
            market_val += val
            st.sidebar.write(f"**{t}:** ${val:,.2f}")

    # שווי תיק כולל
    total_portfolio = market_val + current_cash
    st.sidebar.divider()
    st.sidebar.metric("שווי תיק כולל", f"${total_portfolio:,.2f}", delta=f"${total_portfolio - initial_value_dec_25:,.2f}")

    # --- תצוגה מרכזית ---
    st.link_button("📂 פתח גיליון לעדכון", SHEET_URL, use_container_width=True, type="primary")
    t1, t2 = st.tabs(["🔓 פתוחים", "🔒 סגורים"])
    with t1: st.dataframe(open_trades, use_container_width=True)
    with t2: st.dataframe(closed_trades, use_container_width=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
