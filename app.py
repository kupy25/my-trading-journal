import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
import plotly.express as px

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק ומעקב טריידים - 2026")

SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

# --- נתוני אמת (נכון לרגע זה) ---
CASH_NOW = 4957.18  # המזומן שיש לך פיזית בחשבון עכשיו
initial_portfolio_value = 44302.55 # שווי התיק בנקודת הייחוס (31.12.25)

conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # 1. קריאת נתונים
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()

    # 2. המרת עמודות למספרים
    cols_to_fix = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'עלות יציאה', 'PnL']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 3. הפרדת טריידים
    # טריידים פתוחים (אלו שמושקעים בהם ה-48,031.75$)
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    # טריידים שנסגרו (אנחנו נחשב רק כאלו שיינסגרו מעכשיו והלאה)
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # --- לוגיקת מזומן פנוי מעודכנת ---
    # המזומן שיש לך עכשיו הוא הנתון הקובע. 
    # כל פעם שתמכור מניה שקיימת כרגע ב-open_trades, המזומן יגדל ב-'עלות יציאה'.
    # כל פעם שתוסיף מניה חדשה לגיליון, המזומן יקטן ב-'עלות כניסה'.
    
    # חישוב: (מזומן נוכחי) + (סך כל עלות היציאה של טריידים שנסגרו בעתיד)
    # כדי לא להסתבך עם העבר, פשוט נציג את המזומן שנתת לי כבסיס קבוע.
    current_cash = CASH_NOW 

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ נתוני חשבון")
    st.sidebar.metric("מזומן פנוי למסחר", f"${current_cash:,.2f}")
    
    total_invested = open_trades['עלות כניסה'].sum()
    st.sidebar.write(f"💰 הון מושקע (ברוטו): ${total_invested:,.2f}")

    # מחשבון גודל פוזיציה
    st.sidebar.divider()
    st.sidebar.subheader("🧮 מחשבון טרייד")
    calc_t = st.sidebar.text_input("טיקר", "").upper()
    e_p = st.sidebar.number_input("כניסה $", value=0.0)
    s_p = st.sidebar.number_input("סטופ $", value=0.0)
    
    if calc_t and e_p > s_p:
        risk_amt = initial_portfolio_value * 0.01 
        qty = min(int(risk_amt / (e_p - s_p)), int(current_cash / e_p))
        if qty > 0:
            st.sidebar.success(f"כמות: {qty} | עלות: ${qty*e_p:,.2f}")
        else: st.sidebar.warning("אין מספיק מזומן פנוי")

    # --- פוזיציות לייב (כאן נראה את ההפסד "על הנייר") ---
    st.sidebar.divider()
    st.sidebar.subheader("📈 פוזיציות (Live)")
    tickers = open_trades['Ticker'].unique()
    market_val_total = 0
    total_unrealized_pnl = 0
    
    if len(tickers) > 0:
        try:
            data = yf.download(list(tickers), period="1d", progress=False)['Close']
            for t in tickers:
                curr = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
                t_rows = open_trades[open_trades['Ticker'] == t]
                
                val = (curr * t_rows['Qty']).sum()
                pnl = ((curr - t_rows['Entry_Price']) * t_rows['Qty']).sum()
                
                market_val_total += val
                total_unrealized_pnl += pnl
                
                st.sidebar.write(f"**{t}:** ${val:,.2f}")
                color = "#00c853" if pnl >= 0 else "#ff4b4b"
                st.sidebar.markdown(f"<p style='color:{color}; margin-top:-15px;'>{'+' if pnl >= 0 else ''}{pnl:,.2f}$</p>", unsafe_allow_html=True)
        except: st.sidebar.write("טוען נתונים...")

    # שווי תיק כולל (מזומן + שווי שוק נוכחי של המניות)
    total_portfolio = market_val_total + current_cash
    st.sidebar.divider()
    st.sidebar.write("### שווי תיק כולל (לייב)")
    st.sidebar.write(f"## ${total_portfolio:,.2f}")
    
    pnl_color = "#00c853" if total_unrealized_pnl >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"רווח/הפסד על הנייר: <b style='color:{pnl_color}'>${total_unrealized_pnl:,.2f}</b>", unsafe_allow_html=True)

    # --- תצוגה מרכזית ---
    st.link_button("📂 פתח גיליון לעדכון", SHEET_URL, use_container_width=True, type="primary")
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    with t1: st.dataframe(open_trades, use_container_width=True)
    with t2: st.dataframe(closed_trades, use_container_width=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
