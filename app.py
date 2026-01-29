import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון (10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key="fixed_reboot_v3")

# 2. קישור ישיר ל-CSV (תחליף את זה בקישור שקיבלת מה-Publish to Web)
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS_O8Bf2M9zL9_9-k7-V6_D0N18ARrpYaHCGPdxF6o9vJvPf0Anpg/pub?output=csv"
PORTFOLIO_START_VAL = 44302.55 

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

try:
    # קריאה ישירה של הנתונים
    df = pd.read_csv(CSV_URL)
    df.columns = df.columns.str.strip()
    
    # ניקוי עמודות
    for col in ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL', 'מזומן_עדכני']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # שליפת מזומן מעמודה N
    if 'מזומן_עדכני' in df.columns:
        cash_series = df['מזומן_עדכני'][df['מזומן_עדכני'] > 0]
        current_cash = float(cash_series.iloc[-1]) if not cash_series.empty else 0.0
    else:
        current_cash = 0.0

    # הפרדה לפתוחות וסגורות
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull())].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # נתוני לייב
    market_val_total = 0
    live_list = []

    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum'}).reset_index()
        tickers = list(summary['Ticker'].unique())
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        for _, row in summary.iterrows():
            t = row['Ticker']
            price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            val = float(price * row['Qty'])
            market_val_total += val
            live_list.append({'Ticker': t, 'שווי': val})
        live_df = pd.DataFrame(live_list)

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${current_cash:,.2f}")
    
    total_val = market_val_total + current_cash
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.subheader("שווי תיק כולל")
    st.sidebar.write(f"## ${total_val:,.2f}")
    
    color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<h3 style='color:{color};'>{'+' if diff >= 0 else ''}{diff:,.2f}$</h3>", unsafe_allow_html=True)

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not live_list:
            st.info("אין פוזיציות פתוחות")
        else:
            st.dataframe(live_df, width=1200) # שימוש ברוחב קבוע למניעת שגיאות
            st.divider()
            pie_data = pd.concat([pd.DataFrame(live_list), pd.DataFrame([{'Ticker': 'מזומן', 'שווי': current_cash}])])
            st.plotly_chart(px.pie(pie_data, values='שווי', names='Ticker', hole=0.4))

    with t2:
        if not closed_trades.empty:
            st.dataframe(closed_trades[['Ticker', 'Qty', 'PnL']])

except Exception as e:
    st.error(f"האתר נתקל בבעיה בטעינת הנתונים: {e}")
