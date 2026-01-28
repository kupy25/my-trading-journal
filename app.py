import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
import datetime

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק ומעקב טריידים - 2026")

# הקישור לגיליון
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

# --- נתוני יסוד ---
initial_value_dec_25 = 44302.55
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # 1. קריאת נתוני הטריידים
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()

    # 2. ניהול מזומן פנוי - שיפור מנגנון הקריאה
    available_cash = 0.0
    cash_info = ""
    try:
        # קריאת כל הגיליונות כדי לוודא ש-Account קיים
        df_acc = conn.read(worksheet="Account", ttl="0")
        df_acc.columns = df_acc.columns.str.strip()
        
        if 'Cash' in df_acc.columns:
            available_cash = float(df_acc['Cash'].iloc[0])
            cash_info = "✅ נתונים מסונכרנים לגיליון Account"
        else:
            available_cash = 5732.40
            cash_info = "❌ עמודת 'Cash' לא נמצאה בגיליון Account"
    except Exception as e:
        available_cash = 5732.40
        cash_info = f"⚠️ שגיאה בגישה לגיליון Account: {str(e)}"

    # טיפול בתאריכים ומספרים
    for date_col in ['Entry_Date', 'Exit_Date']:
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce').dt.date

    numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'עלות יציאה', 'PnL']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # הפרדה לפתוחים וסגורים
    open_trades = df[df['Exit_Price'] == 0].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy().sort_values(by='Exit_Date', ascending=False)

    # --- SIDEBAR: נתוני חשבון ומחשבון ---
    st.sidebar.header("⚙️ נתוני חשבון")
    st.sidebar.metric("מזומן פנוי", f"${available_cash:,.2f}", help=cash_info)
    
    if "⚠️" in cash_info or "❌" in cash_info:
        st.sidebar.warning(cash_info)

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
        final_qty = min(int(money_at_risk / risk_per_share), int(available_cash / entry_p))
        if final_qty > 0:
            st.sidebar.success(f"✅ כמות לקנייה: {final_qty} מניות")
            st.sidebar.write(f"💰 עלות פוזיציה: ${final_qty * entry_p:,.2f}")
            st.sidebar.write(f"📉 סיכון כספי: ${final_qty * risk_per_share:,.2f}")
        else: st.sidebar.error("אין מספיק מזומן פנוי!")

    # --- משיכת נתוני שוק לייב ---
    open_tickers = [str(t).strip().upper() for t in open_trades['Ticker'].dropna().unique()]
    market_data = {}
    if open_tickers:
        data_dl = yf.download(open_tickers, period="1y", group_by='ticker', progress=False)
        for t in open_tickers:
            try:
                t_hist = data_dl[t] if len(open_tickers) > 1 else data_dl
                market_data[t] = {
                    'curr': t_hist['Close'].iloc[-1],
                    'ma150': t_hist['Close'].rolling(window=150).mean().iloc[-1]
                }
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
            p_color = "#00c853" if pnl >= 0 else "#ff4b4b"
            st.sidebar.markdown(f"<p style='color:{p_color}; margin-top:-15px;'>{'+' if pnl >= 0 else ''}{pnl:,.2f}$</p>", unsafe_allow_html=True)

    st.sidebar.divider()
    total_realized_pnl = closed_trades['PnL'].sum()
    st.sidebar.metric("PnL ממומש (מצטבר)", f"${total_realized_pnl:,.2f}")
    
    u_color = "#00c853" if total_unrealized_pnl >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"**PnL לא ממומש:** <span style='color:{u_color};'>${total_unrealized_pnl:,.2f}</span>", unsafe_allow_html=True)

    # שווי כולל
    total_val = market_value_stocks + available_cash
    st.sidebar.divider()
    st.sidebar.metric("שווי תיק כולל", f"${total_val:,.2f}", delta=f"{total_val - initial_value_dec_25:,.2f}$")
    
    # --- תצוגה מרכזית ---
    st.link_button("📂 פתח גיליון גוגל לעדכון טריידים", SHEET_URL, use_container_width=True, type="primary")
    
    tab1, tab2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])

    with tab1:
        st.subheader("פוזיציות פעילות")
        cols_open = ['Ticker', 'Entry_Date', 'Qty', 'Entry_Price', 'עלות כניסה', 'סיבת כניסה']
        st.dataframe(open_trades[[c for c in cols_open if c in open_trades.columns]], use_container_width=True)

    with tab2:
        st.subheader("היסטוריית עסקאות")
        cols_closed = [
            'Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'Entry_Price', 
            'עלות כניסה', 'Exit_Price', 'עלות יציאה', 'PnL', 'סיבת יציאה'
        ]
        st.dataframe(closed_trades[[c for c in cols_closed if c in closed_trades.columns]], use_container_width=True)

except Exception as e:
    st.error(f"שגיאה כללית במערכת: {e}")
