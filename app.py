import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון אוטומטי (10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key="fixed_baseline_v2")

# 2. נתוני בסיס (מעודכנים לפי מה שציינת)
CASH_NOW = 8377.65  
PORTFOLIO_START_VAL = 44302.55 

def get_fee(qty):
    # חישוב עמלה: מינימום 3.5$ או לפי כמות מניות
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

# פונקציה לצביעת טקסט בטבלה (ירוק/אדום)
def color_pnl(val):
    if isinstance(val, (int, float)):
        color = 'red' if val < 0 else 'green'
    else:
        # לטיפול במקרה של מחרוזות אחוזים
        try:
            num = float(str(val).replace('%', '').replace('$', '').replace(',', ''))
            color = 'red' if num < 0 else 'green'
        except:
            return ''
    return f'color: {color}'

# 3. חיבור לגיליון גוגל שיטס
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # קריאת נתונים
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    
    # ניקוי והמרת נתונים למספרים
    numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # הפרדה לפוזיציות פתוחות וסגורות
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # חישוב עמלות מצטברות
    fees_open = open_trades['Qty'].apply(get_fee).sum()
    # בטרייד סגור מחשבים עמלת כניסה + עמלת יציאה
    fees_closed = (closed_trades['Qty'].apply(get_fee).sum() * 2)
    total_fees = fees_open + fees_closed

    # משיכת נתוני לייב מ-Yahoo Finance
    market_val_total = 0
    live_list = []

    if not open_trades.empty:
        # קיבוץ לפי טיקר (למקרה של מספר כניסות לאותה מניה)
        summary = open_trades.groupby('Ticker').agg({
            'Qty': 'sum', 
            'עלות כניסה': 'sum',
            'סיבת כניסה': 'first'
        }).reset_index()
        
        tickers = list(summary['Ticker'].unique())
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        for _, row in summary.iterrows():
            t = row['Ticker']
            # טיפול במקרה של מניה אחת או כמה
            price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            
            val = price * row['Qty']
            market_val_total += val
            avg_cost = row['עלות כניסה'] / row['Qty']
            pnl_usd = (val - row['עלות כניסה']) - get_fee(row['Qty'])
            pnl_pct = ((price - avg_cost) / avg_cost) * 100
            
            live_list.append({
                'Ticker': t, 
                'כמות': row['Qty'], 
                'שווי': val, 
                'רווח_דולרי': pnl_usd, 
                'רווח_אחוז': pnl_pct,
                'סיבת כניסה': row['סיבת כניסה']
            })
        
        live_df = pd.DataFrame(live_list)

    # --- SIDEBAR (סרגל צד) ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${CASH_NOW:,.2f}")
    
    total_val = market_val_total + CASH_NOW
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.write("### שווי תיק כולל")
    st.sidebar.write(f"## ${total_val:,.2f}")
    
    color_sidebar = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{color_sidebar}; font-size: 20px; font-weight: bold; margin-top:-10px;'>{'+' if diff >= 0 else ''}{diff:,.2f}$</p>", unsafe_allow_html=True)
    
    st.sidebar.write("📉 **עמלות מצטברות:**")
    st.sidebar.markdown(f"<p style='color:#ff4b4b; font-size: 18px; font-weight: bold; margin-top:-10px;'>-${total_fees:,.2f}</p>", unsafe_allow_html=True)

    # מחשבון טרייד - מוטמע קבוע
    st.sidebar.divider()
    st.sidebar.subheader("🧮 מחשבון טרייד")
    calc_name = st.sidebar.text_input("שם מניה", "AAPL")
    c_entry = st.sidebar.number_input("כניסה $", value=0.0, step=0.1)
    c_stop = st.sidebar.number_input("סטופ $", value=0.0, step=0.1)
    
    if c_entry > c_stop and c_entry > 0:
        # סיכון של 1% מהתיק המקורי
        risk = PORTFOLIO_START_VAL * 0.01
        qty_to_buy = int(risk / (c_entry - c_stop))
        st.sidebar.success(f"מניה: {calc_name}\n\nכמות: {qty_to_buy}\n\nעלות: ${qty_to_buy * c_entry:,.2f}")

    # --- MAIN SCREEN (מסך ראשי) ---
    st.title("📊 יומן המסחר של אבי")
    
    # כפתור לפתיחת הגיליון (קישור גנרי - מומלץ להחליף בקישור הישיר שלך)
    st.link_button("📂 פתח גוגל שיטס", "https://docs.google.com/spreadsheets")

    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades.empty:
            # עיצוב הטבלה עם צבעים (שימוש ב-map לתיקון השגיאה)
            styled_live = live_df.sort_values('שווי', ascending=False).style.map(
                color_pnl, subset=['רווח_דולרי', 'רווח_אחוז']
            ).format({
                'שווי': '${:,.2f}',
                'רווח_דולרי': '${:,.2f}',
                'רווח_אחוז': '{:.2f}%'
            })
            
            st.dataframe(styled_live, use_container_width=True, hide_index=True)
            
            # תרשים פאי - פיזור תיק
            st.divider()
            pie_data = pd.concat([live_df[['Ticker', 'שווי']].rename(columns={'שווי': 'Value'}), 
                                 pd.DataFrame([{'Ticker': 'מזומן', 'Value': CASH_NOW}])])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Ticker', hole=0.4, title="פיזור תיק כולל"), use_container_width=True)
        else:
            st.info("אין פוזיציות פתוחות כרגע.")

    with t2:
        if not closed_trades.empty:
            realized_total = closed_trades['PnL'].sum()
            st.subheader(f"רווח ממומש מצטבר: ${realized_total:,.2f}")
            
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL', 'סיבת כניסה', 'סיבת יציאה']], 
                         use_container_width=True, hide_index=True)
        else:
            st.info("לא נמצאו טריידים סגורים.")

except Exception as e:
    st.error(f"שגיאה בהרצת האפליקציה: {e}")
