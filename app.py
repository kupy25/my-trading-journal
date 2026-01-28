import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק - תצוגת פוזיציות מאוחדת")

# הקישור לגיליון שלך
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

# --- נתוני אמת קבועים ---
CASH_NOW = 4957.18 
initial_portfolio_value = 44302.55

conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # 1. קריאת נתונים
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()

    # 2. פונקציית עמלה לפי טבלת הברוקר (3.5$ + 0.0078$ למניה)
    def calculate_trade_fee(qty):
        return 3.50 + (qty * 0.0078) if qty > 0 else 0

    # 3. המרת עמודות למספרים
    numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'עלות יציאה', 'PnL']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 4. הפרדה לפתוחים וסגורים
    raw_open = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # --- איחוד אוטומטי לכל המניות בתיק ---
    if not raw_open.empty:
        # חישוב עמלת קנייה לכל רכישה בנפרד (כי על כל חיזוק משלמים עמלה)
        raw_open['temp_fee'] = raw_open['Qty'].apply(calculate_trade_fee)
        
        # המנוע שסורק ומאחד טיקרים זהים
        open_trades = raw_open.groupby('Ticker').agg({
            'Qty': 'sum',
            'עלות כניסה': 'sum',
            'temp_fee': 'sum',
            'Entry_Date': 'min'  # מציג את תאריך הכניסה הראשון
        }).reset_index()
        
        # חישוב מחיר כניסה ממוצע משוקלל לכל פוזיציה מאוחדת
        open_trades['Entry_Price'] = open_trades['עלות כניסה'] / open_trades['Qty']
        open_trades.rename(columns={'temp_fee': 'סך עמלות קנייה'}, inplace=True)
    else:
        open_trades = pd.DataFrame()

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ נתוני חשבון")
    st.sidebar.metric("מזומן פנוי", f"${CASH_NOW:,.2f}")

    # --- פוזיציות לייב (מאוחדות) ב-Sidebar ---
    st.sidebar.divider()
    st.sidebar.subheader("📈 פוזיציות מאוחדות (Live)")
    
    market_val_total = 0
    total_unrealized_pnl = 0
    
    if not open_trades.empty:
        tickers = open_trades['Ticker'].unique()
        try:
            # משיכת נתונים לכל הטיקרים במכה אחת
            data = yf.download(list(tickers), period="1d", progress=False)['Close']
            
            for _, row in open_trades.iterrows():
                t = row['Ticker']
                # שליפת המחיר האחרון
                curr = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
                
                val = curr * row['Qty']
                # רווח/הפסד נטו (שווי שוק פחות עלות כניסה פחות עמלות)
                pnl = (val - row['עלות כניסה']) - row['סך עמלות קנייה']
                
                market_val_total += val
                total_unrealized_pnl += pnl
                
                st.sidebar.write(f"**{t}:** ${val:,.2f} (ממוצע: ${row['Entry_Price']:.2f})")
                color = "#00c853" if pnl >= 0 else "#ff4b4b"
                st.sidebar.markdown(f"<p style='color:{color}; margin-top:-15px;'>{'+' if pnl >= 0 else ''}{pnl:,.2f}$ נטו</p>", unsafe_allow_html=True)
        except:
            st.sidebar.info("מתחבר לנתוני בורסה...")

    # סיכום שווי תיק
    total_portfolio = market_val_total + CASH_NOW
    st.sidebar.divider()
    st.sidebar.metric("שווי תיק כולל", f"${total_portfolio:,.2f}", 
                      delta=f"${total_unrealized_pnl:,.2f} (על הנייר)")

    # --- תצוגה מרכזית ---
    st.link_button("📂 פתח גיליון לעדכון", SHEET_URL, use_container_width=True, type="primary")
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות (מאוחד)", "🔒 טריידים סגורים"])
    
    with t1:
        st.subheader("ריכוז פוזיציות פעילות")
        if not open_trades.empty:
            # סידור הטבלה לתצוגה נוחה
            display_df = open_trades[['Ticker', 'Entry_Date', 'Qty', 'Entry_Price', 'עלות כניסה', 'סך עמלות קנייה']]
            st.dataframe(display_df.sort_values('עלות כניסה', ascending=False), use_container_width=True)
        else:
            st.write("אין פוזיציות פתוחות כרגע.")

    with t2:
        st.subheader("היסטוריית טריידים")
        if not closed_trades.empty:
            st.dataframe(closed_trades.sort_values('Exit_Date', ascending=False), use_container_width=True)
        else:
            st.write("טרם נסגרו טריידים.")

except Exception as e:
    st.error(f"שגיאה בעיבוד הנתונים: {e}")
