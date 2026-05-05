import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=15000, key="datarefresh")

# --- נתונים מעודכנים לפי הדיווח שלך ---
CASH_VAL_FIXED = 9535.30      # מזומן פנוי לפי הברוקר
PORTFOLIO_BROKER_VAL = 40448.3 # שווי תיק כולל לפי הברוקר
PORTFOLIO_START_VAL = 44302.55 # שווי התחלתי לחישוב רווח כללי
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

# 2. חיבור וקריאת נתונים
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    
    # ניקוי עמודות נומריות
    numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # הפרדה לפוזיציות פתוחות וסגורות
    open_trades_raw = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    market_val_total = 0
    live_list = []

    if not open_trades_raw.empty:
        # איחוד פוזיציות לפי טיקר (חישוב מחיר ממוצע וסך כמות)
        summary = open_trades_raw.groupby('Ticker').agg({
            'Qty': 'sum', 
            'עלות כניסה': 'sum',
            'סיבת כניסה': 'first'
        }).reset_index()
        
        tickers = list(summary['Ticker'].unique())
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        for _, row in summary.iterrows():
            t = row['Ticker']
            try:
                # חילוץ מחיר שוק נוכחי
                if len(tickers) > 1:
                    price = data[t].dropna().iloc[-1]
                else:
                    price = data.dropna().iloc[-1]
                
                qty = row['Qty']
                total_cost = row['עלות כניסה']
                val = price * qty
                market_val_total += val
                
                avg_price = total_cost / qty if qty != 0 else 0
                pnl_usd = (val - total_cost) - get_fee(qty)
                pnl_pct = ((price - avg_price) / avg_price) * 100 if avg_price != 0 else 0
                
                live_list.append({
                    'Ticker': t, 
                    'כמות': qty, 
                    'מחיר ממוצע': avg_price,
                    'מחיר שוק': price,
                    'שווי פוזיציה': val, 
                    'רווח $': pnl_usd, 
                    'רווח %': pnl_pct, 
                    'סיבת כניסה': row['סיבת כניסה']
                })
            except: continue
        
        live_df = pd.DataFrame(live_list)

    # --- חישוב שווי תיק כולל (Live) ---
    # שווי התיק האמיתי = מזומן פנוי בברוקר + שווי שוק נוכחי של המניות
    total_portfolio_live = CASH_VAL_FIXED + market_val_total
    diff_from_start = total_portfolio_live - PORTFOLIO_START_VAL

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${CASH_VAL_FIXED:,.2f}")
    st.sidebar.metric("שווי מניות (Live)", f"${market_val_total:,.2f}")
    
    st.sidebar.divider()
    st.sidebar.write("### שווי תיק כולל (Live)")
    st.sidebar.write(f"## ${total_portfolio_live:,.2f}")
    
    color = "#00c853" if diff_from_start >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{color}; font-size: 20px; font-weight: bold; margin-top:-10px;'>{'+' if diff_from_start >= 0 else ''}{diff_from_start:,.2f}$</p>", unsafe_allow_html=True)
    
    # מחשבון טרייד
    st.sidebar.divider()
    st.sidebar.subheader("🧮 מחשבון טרייד (סיכון 1%)")
    calc_ticker = st.sidebar.text_input("סימול מניה", value="AAPL")
    c_entry = st.sidebar.number_input("מחיר כניסה $", value=0.0)
    c_stop = st.sidebar.number_input("מחיר סטופ $", value=0.0)
    
    if c_entry > c_stop and c_stop > 0:
        risk_amount = PORTFOLIO_BROKER_VAL * 0.01
        q = int(risk_amount / (c_entry - c_stop))
        st.sidebar.success(f"מניה: {calc_ticker}\n\nכמות: {q} יח'\n\nעלות: ${q*c_entry:,.2f}")

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    st.link_button("📂 פתח את גיליון הגוגל שיטס", SHEET_URL)

    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not live_list == []:
            # עיצוב טבלה
            def color_pnl(val):
                return f'color: {"green" if val > 0 else "red"}'
            
            styled_df = live_df.style.map(color_pnl, subset=['רווח $', 'רווח %'])\
                                     .format({
                                         'מחיר ממוצע': "{:.2f}$",
                                         'מחיר שוק': "{:.2f}$",
                                         'שווי פוזיציה': "{:,.2f}$", 
                                         'רווח $': "{:,.2f}$", 
                                         'רווח %': "{:.2f}%"
                                     })
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            st.divider()
            # גרף פאי מאוחד - מראה כל מניה כחלק מהתיק כולל המזומן
            pie_data = pd.concat([
                live_df[['Ticker', 'שווי פוזיציה']].rename(columns={'שווי פוזיציה': 'Value'}), 
                pd.DataFrame([{'Ticker': 'CASH', 'Value': CASH_VAL_FIXED}])
            ])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Ticker', hole=0.4, title="פיזור תיק כולל (כולל מזומן)"), use_container_width=True)
        else:
            st.info("אין פוזיציות פתוחות להצגה.")

    with t2:
        if not closed_trades.empty:
            total_realized = closed_trades['PnL'].sum()
            st.metric("סך רווח ממומש (כללי)", f"${total_realized:,.2f}")
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL', 'סיבת כניסה']].sort_values('Exit_Date', ascending=False), 
                         use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
