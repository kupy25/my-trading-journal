import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh
import datetime

# 1. הגדרות דף ורענון אוטומטי (10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key="full_restore_verified")

# 2. נתוני בסיס קבועים (לפי הוראת המשתמש)
CASH_NOW = 8377.65  
PORTFOLIO_START_VAL = 44302.55 

def get_fee(qty):
    # חישוב עמלות לפי טבלת הברוקר: $3.50 + עמלות משתנות של $0.0078 למניה
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

# פונקציית עזר לעיצוב צבעים בטבלה
def color_pnl(val):
    color = 'red' if (isinstance(val, (int, float)) and val < 0) else 'green'
    return f'color: {color}; font-weight: bold;'

# 3. חיבור לגיליון
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    
    # המרת עמודות למספרים
    numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # הפרדה בין פתוחים לסגורים
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # חישובי עמלות מצטברות
    fees_open = open_trades['Qty'].apply(get_fee).sum()
    fees_closed = (closed_trades['Qty'].apply(get_fee).sum() * 2) # קניה ומכירה
    total_fees = fees_open + fees_closed

    # משיכת נתוני לייב
    market_val_total = 0
    live_list = []

    if not open_trades.empty:
        # איחוד פוזיציות לפי טיקר (מחיר ממוצע)
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum', 'סיבת כניסה': 'first'}).reset_index()
        tickers = list(summary['Ticker'].unique())
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        for _, row in summary.iterrows():
            t = row['Ticker']
            # טיפול במשיכה של מניה בודדת לעומת רשימה
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

    # --- SIDEBAR (עיצוב מחדש) ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${CASH_NOW:,.2f}")
    
    total_val = market_val_total + CASH_NOW
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.write("### שווי תיק כולל")
    st.sidebar.write(f"## ${total_val:,.2f}")
    
    color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{color}; font-size: 20px; font-weight: bold; margin-top:-10px;'>{'+' if diff >= 0 else ''}{diff:,.2f}$</p>", unsafe_allow_html=True)
    
    st.sidebar.write("📉 **עמלות מצטברות:**")
    st.sidebar.markdown(f"<p style='color:#ff4b4b; font-size: 18px; font-weight: bold; margin-top:-10px;'>-${total_fees:,.2f}</p>", unsafe_allow_html=True)

    # מחשבון טרייד משופר
    st.sidebar.divider()
    with st.sidebar.expander("🧮 מחשבון טרייד חדש"):
        calc_t = st.text_input("שם מניה", value="TSLA").upper()
        c_entry = st.number_input("מחיר כניסה $", value=0.0)
        c_stop = st.number_input("מחיר סטופ $", value=0.0)
        if c_entry > c_stop:
            risk_amt = PORTFOLIO_START_VAL * 0.01 # סיכון 1% מהתיק
            qty = int(risk_amt / (c_entry - c_stop))
            st.success(f"לקנות {qty} מניות {calc_t}")
            st.info(f"עלות כוללת: ${qty*c_entry:,.2f}")

    # --- מסך ראשי ---
    col_header, col_link = st.columns([4, 1])
    with col_header:
        st.title("📊 יומן המסחר של אבי")
    with col_link:
        st.link_button("📂 פתח גוגל שיט", "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit")

    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades.empty:
            # הצגת טבלה מעוצבת עם צבעים
            df_display = live_df.copy()
            st.dataframe(
                df_display.style.applymap(color_pnl, subset=['רווח_דולרי', 'רווח_אחוז']),
                use_container_width=True,
                hide_index=True
            )
            
            st.divider()
            st.subheader("🥧 התפלגות תיק (כולל מזומן)")
            # הכנת נתונים לגרף עוגה
            pie_data = pd.concat([
                live_df[['Ticker', 'שווי']].rename(columns={'שווי': 'Value'}), 
                pd.DataFrame([{'Ticker': 'מזומן', 'Value': CASH_NOW}])
            ])
            fig = px.pie(pie_data, values='Value', names='Ticker', hole=0.4)
            fig.update_traces(textinfo='percent+label') # הוספת לייבלים
            st.plotly_chart(fig, use_container_width=True)

    with t2:
        if not closed_trades.empty:
            realized = closed_trades['PnL'].sum()
            st.markdown(f"### סך רווח ממומש (YTD): <span style='color:{'green' if realized >=0 else 'red'};'>${realized:,.2f}</span>", unsafe_allow_html=True)
            st.dataframe(
                closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL', 'סיבת כניסה', 'סיבת יציאה']].sort_values('Exit_Date', ascending=False),
                use_container_width=True,
                hide_index=True
            )

except Exception as e:
    st.error(f"שגיאה בטעינת הנתונים: {e}")
