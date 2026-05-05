import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון אוטומטי (כל 15 שניות)
st.set_page_config(page_title="יומן המסחר של אבי - גרסה יציבה", layout="wide")
st_autorefresh(interval=15000, key="datarefresh")

# --- נתוני יסוד קבועים ---
CASH_VAL_FIXED = 9535.30       # מזומן פנוי לפי הברוקר
PORTFOLIO_START_VAL = 44302.55 # שווי תיק התחלתי (לחישוב PnL כולל)
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

def get_fee(qty):
    """חישוב עמלת מסחר משוערת"""
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

# 2. חיבור וקריאת נתונים מ-Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    
    # המרת עמודות למספרים וניקוי שגיאות
    numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # הפרדה לפוזיציות פתוחות (רק אלו ללא מחיר יציאה)
    open_trades_raw = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    market_val_total = 0
    live_list = []

    # 3. עיבוד פוזיציות פתוחות ואיחוד טיקרים
    if not open_trades_raw.empty:
        summary = open_trades_raw.groupby('Ticker').agg({
            'Qty': 'sum', 
            'עלות כניסה': 'sum',
            'סיבת כניסה': 'first'
        }).reset_index()
        
        tickers = list(summary['Ticker'].unique())
        # הורדת נתוני שוק חיים
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        for _, row in summary.iterrows():
            t = row['Ticker']
            try:
                # חילוץ מחיר אחרון (טיפול במקרה של טיקר אחד או יותר)
                current_market_price = data[t].dropna().iloc[-1] if len(tickers) > 1 else data.dropna().iloc[-1]
                
                qty = row['Qty']
                total_cost = row['עלות כניסה']
                position_market_value = current_market_price * qty
                market_val_total += position_market_value
                
                avg_entry_price = total_cost / qty if qty != 0 else 0
                pnl_usd = (position_market_value - total_cost) - get_fee(qty)
                pnl_pct = ((current_market_price - avg_entry_price) / avg_entry_price) * 100 if avg_entry_price != 0 else 0
                
                live_list.append({
                    'Ticker': t, 
                    'כמות': qty, 
                    'מחיר ממוצע': avg_entry_price,
                    'מחיר שוק': current_market_price,
                    'שווי פוזיציה': position_market_value, 
                    'רווח $': pnl_usd, 
                    'רווח %': pnl_pct, 
                    'סיבת כניסה': row['סיבת כניסה']
                })
            except: continue
        
        live_df = pd.DataFrame(live_list)

    # --- חישובים סופיים ---
    total_portfolio_live = CASH_VAL_FIXED + market_val_total
    all_time_diff = total_portfolio_live - PORTFOLIO_START_VAL

    # --- SIDEBAR: ניהול חשבון ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${CASH_VAL_FIXED:,.2f}")
    st.sidebar.metric("שווי מניות (Live)", f"${market_val_total:,.2f}")
    
    st.sidebar.divider()
    st.sidebar.subheader("שווי תיק כולל (Live)")
    st.sidebar.title(f"${total_portfolio_live:,.2f}")
    
    pnl_color = "#00c853" if all_time_diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{pnl_color}; font-size: 20px; font-weight: bold; margin-top:-10px;'>{'+' if all_time_diff >= 0 else ''}{all_time_diff:,.2f}$ (PnL כללי)</p>", unsafe_allow_html=True)
    
    # מחשבון ניהול סיכונים
    st.sidebar.divider()
    st.sidebar.subheader("🧮 מחשבון טרייד (סיכון 1%)")
    calc_ticker = st.sidebar.text_input("סימול מניה", value="AAPL")
    c_entry = st.sidebar.number_input("מחיר כניסה $", value=0.0)
    c_stop = st.sidebar.number_input("מחיר סטופ $", value=0.0)
    
    if c_entry > c_stop and c_stop > 0:
        risk_per_trade = total_portfolio_live * 0.01
        shares_to_buy = int(risk_per_trade / (c_entry - c_stop))
        st.sidebar.success(f"כמות לקנייה: {shares_to_buy} יח'\n\nחשיפה: ${shares_to_buy*c_entry:,.2f}")

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    st.link_button("📂 פתח גיליון Google Sheets", SHEET_URL)

    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if live_list:
            # עיצוב והצגת טבלת פוזיציות חיות
            def apply_color(val):
                return f'color: {"green" if val > 0 else "red"}'
            
            formatted_live_df = live_df.style.map(apply_color, subset=['רווח $', 'רווח %'])\
                                     .format({
                                         'מחיר ממוצע': "{:.2f}$",
                                         'מחיר שוק': "{:.2f}$",
                                         'שווי פוזיציה': "{:,.2f}$", 
                                         'רווח $': "{:,.2f}$", 
                                         'רווח %': "{:.2f}%"
                                     })
            st.dataframe(formatted_live_df, use_container_width=True, hide_index=True)
            
            st.divider()
            # גרף פאי של פיזור הנכסים
            pie_data = pd.concat([
                live_df[['Ticker', 'שווי פוזיציה']].rename(columns={'שווי פוזיציה': 'Value'}), 
                pd.DataFrame([{'Ticker': 'מזומן פנוי', 'Value': CASH_VAL_FIXED}])
            ])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Ticker', hole=0.4, title="פיזור הון ריאלי"), use_container_width=True)
        else:
            st.info("אין פוזיציות פתוחות כרגע. ברגע שתזין קנייה בגיליון ללא מחיר יציאה, היא תופיע כאן.")

    with t2:
        if not closed_trades.empty:
            st.metric("סך רווח ממומש", f"${closed_trades['PnL'].sum():,.2f}")
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL', 'סיבת כניסה']].sort_values('Exit_Date', ascending=False), 
                         use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה בטעינת הנתונים: {e}")
