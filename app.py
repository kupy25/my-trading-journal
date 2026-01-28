import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
import datetime

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק ומעקב טריידים - 2026")

SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

# --- נתוני יסוד ---
initial_value_dec_25 = 44302.55
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # 1. קריאת הנתונים וניקוי כותרות
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip().str.replace(' ', '_')

    # 2. איתור מזומן בסיס (מנגנון חיפוש גמיש)
    base_cash = 0.0
    cash_col = [c for c in df.columns if 'מזומן' in c]
    
    if cash_col:
        # לוקח את הערך המספרי הראשון בעמודה שמצאנו
        valid_cash = pd.to_numeric(df[cash_col[0]], errors='coerce').dropna()
        if not valid_cash.empty:
            base_cash = float(valid_cash.iloc[0])

    # 3. טיפול בתאריכים ומספרים בטריידים
    for date_col in ['Entry_Date', 'Exit_Date']:
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce').dt.date

    numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות_כניסה', 'עלות_יציאה', 'PnL']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # הפרדה לפתוחים וסגורים
    open_trades = df[df['Exit_Price'] == 0].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy().sort_values(by='Exit_Date', ascending=False)

    # --- חישוב מזומן דינמי (אוטומציה מלאה) ---
    # עלות פוזיציות שכרגע פתוחות (מוריד מהמזומן)
    total_cost_open = open_trades['עלות_כניסה'].sum() if 'עלות_כניסה' in open_trades.columns else 0
    
    # כסף שחזר ממכירות (מוסיף למזומן)
    total_returned_from_closed = closed_trades['עלות_יציאה'].sum() if 'עלות_יציאה' in closed_trades.columns else 0
    
    # יתרה סופית
    current_available_cash = base_cash - total_cost_open + total_returned_from_closed

    # --- SIDEBAR: נתוני חשבון ---
    st.sidebar.header("⚙️ נתוני חשבון")
    st.sidebar.metric("מזומן פנוי (דינמי)", f"${current_available_cash:,.2f}", 
                      delta=f"בסיס: ${base_cash:,.2f}", delta_color="off")
    
    st.sidebar.caption("💡 המזומן מתעדכן אוטומטית עם כל קנייה או מכירה בגיליון.")

    # מחשבון גודל פוזיציה
    st.sidebar.divider()
    st.sidebar.subheader("🧮 מחשבון טרייד חדש")
    calc_ticker = st.sidebar.text_input("טיקר לבדיקה", value="").strip().upper()
    entry_p = st.sidebar.number_input("מחיר כניסה ($)", min_value=0.0, step=0.01)
    stop_p = st.sidebar.number_input("סטופ לוס ($)", min_value=0.0, step=0.01)
    risk_pct = st.sidebar.slider("סיכון מהתיק (%)", 0.25, 2.0, 1.0, 0.25)

    if calc_ticker and entry_p > stop_p:
        money_at_risk = initial_value_dec_25 * (risk_pct / 100)
        risk_per_share = entry_p - stop_p
        # הגבלה לפי המזומן הדינמי המעודכן
        final_qty = min(int(money_at_risk / risk_per_share), int(current_available_cash / entry_p))
        if final_qty > 0:
            st.sidebar.success(f"✅ כמות לקנייה: {final_qty} מניות")
            st.sidebar.write(f"💰 עלות: ${final_qty * entry_p:,.2f}")
        else: st.sidebar.error("אין מספיק מזומן פנוי!")

    # --- משיכת נתוני שוק לייב ---
    open_tickers = [str(t).strip().upper() for t in open_trades['Ticker'].dropna().unique()]
    market_data = {}
    if open_tickers:
        data_dl = yf.download(open_tickers, period="1y", group_by='ticker', progress=False)
        for t in open_tickers:
            try:
                t_hist = data_dl[t] if len(open_tickers) > 1 else data_dl
                market_data[t] = {'curr': t_hist['Close'].iloc[-1], 'ma150': t_hist['Close'].rolling(window=150).mean().iloc[-1]}
            except: continue

    # --- SIDEBAR: פוזיציות וביצועים ---
    st.sidebar.divider()
    st.sidebar.subheader("📈 פוזיציות פתוחות (Live)")
    market_value_stocks = 0
    total_unrealized_pnl = 0
    for _, row in open_trades.iterrows():
        t = str(row['Ticker']).strip().upper()
        if t in market_data:
            curr = market_data[t]['curr']
            pnl = (curr - row['Entry_Price']) * row['Qty']
            pos_val = curr * row['Qty']
            market_value_stocks += pos_val
            total_unrealized_pnl += pnl
            st.sidebar.write(f"**{t}:** {pos_val:,.2f}$")
            st.sidebar.markdown(f"<p style='color:{'#00c853' if pnl >= 0 else '#ff4b4b'}; margin-top:-15px;'>{'+' if pnl >= 0 else ''}{pnl:,.2f}$</p>", unsafe_allow_html=True)

    st.sidebar.divider()
    total_realized_pnl = closed_trades['PnL'].sum()
    st.sidebar.metric("PnL ממומש (מצטבר)", f"${total_realized_pnl:,.2f}")
    
    u_color = "#00c853" if total_unrealized_pnl >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"**PnL לא ממומש:** <span style='color:{u_color};'>${total_unrealized_pnl:,.2f}</span>", unsafe_allow_html=True)

    total_val = market_value_stocks + current_available_cash
    st.sidebar.divider()
    st.sidebar.metric("שווי תיק כולל", f"${total_val:,.2f}", delta=f"{total_val - initial_value_dec_25:,.2f}$")
    
    st.link_button("📂 פתח גיליון גוגל לעדכון טריידים", SHEET_URL, use_container_width=True, type="primary")
    
    tab1, tab2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    with tab1:
        st.dataframe(open_trades[['Ticker', 'Entry_Date', 'Qty', 'Entry_Price', 'עלות_כניסה', 'סיבת_כניסה']], use_container_width=True)
    with tab2:
        st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'Entry_Price', 'עלות_כניסה', 'Exit_Price', 'עלות_יציאה', 'PnL', 'סיבת_יציאה']], use_container_width=True)

except Exception as e:
    st.error(f"שגיאה כללית: {e}")
