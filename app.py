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
    # 1. קריאת נתונים וניקוי כותרות
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()

    # 2. שליפת מזומן בסיס (מחפש בעמודה L כפי שמופיע בצילום המסך)
    base_cash = 0.0
    # חיפוש עמודה שנקראת Cash_Base או מכילה 'מזומן'
    cash_col = [c for c in df.columns if 'Cash' in c or 'מזומן' in c]
    
    if cash_col:
        # לוקח את הערך הכי גבוה בעמודה (כדי למצוא את ה-4,957.18 גם אם יש שורות ריקות)
        cash_values = pd.to_numeric(df[cash_col[0]], errors='coerce').dropna()
        if not cash_values.empty:
            base_cash = float(cash_values.max())

    # 3. המרת עמודות למספרים (שימוש בשמות המדויקים מהגיליון שלך)
    # שימוש ב-fillna(0) כדי למנוע טעויות חישוב בטריידים פתוחים
    cols_to_fix = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'עלות יציאה', 'PnL']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # הפרדה לפתוחים וסגורים
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull())].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # --- חישוב מזומן דינמי אוטומטי ---
    # קניות: סכום עלות הכניסה של כל המניות שכרגע בתיק
    total_spent_on_open = open_trades['עלות כניסה'].sum()
    
    # מכירות: סכום עלות היציאה של כל מה שמכרת (הכסף שחזר לקופה)
    total_received_from_closed = closed_trades['עלות יציאה'].sum()
    
    # הנוסחה: בסיס פחות קניות פלוס מכירות
    current_cash = base_cash - total_spent_on_open + total_received_from_closed

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ נתוני חשבון")
    
    # הצגת המזומן
    st.sidebar.metric("מזומן פנוי (דינמי)", f"${current_cash:,.2f}")
    st.sidebar.caption(f"בסיס בגיליון: ${base_cash:,.2f}")
    
    if base_cash == 0:
        st.sidebar.error("⚠️ המערכת לא מוצאת את מזומן הבסיס בעמודה L. וודא שהכותרת היא Cash_Base.")

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
        else: st.sidebar.warning("אין מספיק מזומן פנוי לטרייד הזה")

    # --- פוזיציות לייב ב-Sidebar ---
    st.sidebar.divider()
    st.sidebar.subheader("📈 פוזיציות (Live)")
    tickers = open_trades['Ticker'].dropna().unique()
    market_val_total = 0
    
    if len(tickers) > 0:
        try:
            data = yf.download(list(tickers), period="1d", progress=False)['Close']
            for t in tickers:
                # טיפול במקרה של מניה בודדת או רשימה
                curr = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
                t_rows = open_trades[open_trades['Ticker'] == t]
                val = (curr * t_rows['Qty']).sum()
                pnl = ((curr - t_rows['Entry_Price']) * t_rows['Qty']).sum()
                market_val_total += val
                
                st.sidebar.write(f"**{t}:** ${val:,.2f}")
                color = "#00c853" if pnl >= 0 else "#ff4b4b"
                st.sidebar.markdown(f"<p style='color:{color}; margin-top:-15px;'>{'+' if pnl >= 0 else ''}{pnl:,.2f}$</p>", unsafe_allow_html=True)
        except: st.sidebar.write("טוען נתוני שוק...")

    # שווי תיק כולל
    total_portfolio = market_val_total + current_cash
    st.sidebar.divider()
    st.sidebar.metric("שווי תיק כולל", f"${total_portfolio:,.2f}", 
                      delta=f"${total_portfolio - initial_value_dec_25:,.2f}")

    # --- תצוגה מרכזית ---
    st.link_button("📂 פתח גיליון לעדכון", SHEET_URL, use_container_width=True, type="primary")
    
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    with t1:
        st.dataframe(open_trades[['Ticker', 'Entry_Date', 'Qty', 'Entry_Price', 'עלות כניסה', 'סיבת כניסה']], use_container_width=True)
    with t2:
        st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'Entry_Price', 'עלות כניסה', 'Exit_Price', 'עלות יציאה', 'PnL', 'סיבת יציאה']], use_container_width=True)

except Exception as e:
    st.error(f"שגיאה במערכת: {e}")
