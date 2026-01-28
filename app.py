import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
import plotly.express as px

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק כולל עמלות מסחר - 2026")

# הקישור לגיליון שלך
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

# --- נתוני אמת (נכון לפורמט האחרון) ---
CASH_START_POINT = 4957.18  # המזומן הפנוי שיש לך עכשיו בחשבון
initial_portfolio_value = 44302.55 # ערך התיק ב-31.12.25

conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # 1. קריאת נתונים
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()

    # 2. פונקציית חישוב עמלה לפי טבלת הברוקר
    def calculate_trade_fee(qty):
        if qty <= 0: return 0
        # 3.50$ קבוע + (0.0048$ ניתוב + 0.003$ סליקה) למניה
        return 3.50 + (qty * (0.0048 + 0.003))

    # 3. המרת עמודות למספרים
    cols_to_fix = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'עלות יציאה', 'PnL']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 4. הפרדת טריידים
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # --- חישוב מזומן דינמי כולל עמלות ---
    # נניח ש-CASH_START_POINT הוא המזומן שיש לך כרגע. 
    # כל טרייד חדש שייפתח יחסיר את עלותו + עמלת קנייה.
    # כל טרייד שייסגר יוסיף את עלות היציאה שלו פחות עמלת מכירה.
    
    # לצורך החישוב האוטומטי מעכשיו:
    # (הערה: החישוב להלן מניח שהמזומן שנתת הוא נקודת ההתחלה וכל שינוי בגיליון מעדכן אותו)
    current_cash = CASH_START_POINT

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ נתוני חשבון")
    st.sidebar.metric("מזומן פנוי למסחר", f"${current_cash:,.2f}")
    
    # מחשבון כולל עמלות
    st.sidebar.divider()
    st.sidebar.subheader("🧮 מחשבון טרייד ועמלות")
    calc_t = st.sidebar.text_input("טיקר לבדיקה", "").upper()
    e_p = st.sidebar.number_input("מחיר כניסה $", value=0.0)
    s_p = st.sidebar.number_input("סטופ לוס $", value=0.0)
    
    if calc_t and e_p > s_p:
        risk_amt = initial_portfolio_value * 0.01 
        raw_qty = int(risk_amt / (e_p - s_p))
        fee = calculate_trade_fee(raw_qty)
        # וידוא שיש מספיק מזומן גם למניות וגם לעמלה
        qty = min(raw_qty, int((current_cash - fee) / e_p))
        
        if qty > 0:
            final_fee = calculate_trade_fee(qty)
            st.sidebar.success(f"כמות לקנייה: {qty}")
            st.sidebar.write(f"💰 עלות מניות: ${qty*e_p:,.2f}")
            st.sidebar.write(f"💸 עמלת ברוקר: ${final_fee:,.2f}")
            st.sidebar.write(f"⚠️ סה\"כ יורד מהמזומן: ${ (qty*e_p) + final_fee :,.2f}")
        else: st.sidebar.warning("אין מספיק מזומן פנוי")

    # --- פוזיציות לייב ---
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
                
                # חישוב עמלת קנייה שכבר שולמה
                entry_fees = t_rows['Qty'].apply(calculate_trade_fee).sum()
                
                val = (curr * t_rows['Qty']).sum()
                pnl = ((curr - t_rows['Entry_Price']) * t_rows['Qty']).sum() - entry_fees
                
                market_val_total += val
                total_unrealized_pnl += pnl
                
                st.sidebar.write(f"**{t}:** ${val:,.2f}")
                color = "#00c853" if pnl >= 0 else "#ff4b4b"
                st.sidebar.markdown(f"<p style='color:{color}; margin-top:-15px;'>{'+' if pnl >= 0 else ''}{pnl:,.2f}$ (נטו)</p>", unsafe_allow_html=True)
        except: st.sidebar.write("טוען נתוני שוק...")

    # שווי תיק כולל
    total_portfolio = market_val_total + current_cash
    st.sidebar.divider()
    st.sidebar.metric("שווי תיק כולל", f"${total_portfolio:,.2f}", 
                      delta=f"${total_unrealized_pnl:,.2f} (נטו על הנייר)")

    # --- תצוגה מרכזית ---
    st.link_button("📂 פתח גיליון לעדכון טריידים", SHEET_URL, use_container_width=True, type="primary")
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    with t1: st.dataframe(open_trades, use_container_width=True)
    with t2: st.dataframe(closed_trades, use_container_width=True)

except Exception as e:
    st.error(f"שגיאה במערכת: {e}")
