import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import time

# 1. הגדרות דף ורענון (10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
# מפתח רענון שמשתנה עם הזמן כדי להכריח את הדפדפן להתעורר
st_autorefresh(interval=10000, key=f"refresh_{int(time.time() // 10)}")

# 2. קישור ה-CSV שלך (חובה להחליף בקישור מה-Publish to Web)
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQKaG_u8xiC5wYWL3QihjRCsS8FA1O3hjvIWnCwmh3k4yPOK_5scHuwlURvHZjwj3Zo3QWEMse_pK5i/pub?output=csv"
PORTFOLIO_START_VAL = 44302.55 

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

try:
    # 3. קריאת נתונים עם "עוקף מטמון" - מוסיף מספר רנדומלי לסוף הקישור
    cache_buster = f"&cache={int(time.time())}"
    df = pd.read_csv(CSV_URL + cache_buster)
    df.columns = df.columns.str.strip()
    
    # המרת עמודות למספרים
    numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL', 'מזומן_עדכני']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 4. שליפת מזומן מעמודה N (מזומן_עדכני)
    if 'מזומן_עדכני' in df.columns:
        cash_series = df['מזומן_עדכני'][df['מזומן_עדכני'] > 0]
        current_cash = float(cash_series.iloc[-1]) if not cash_series.empty else 0.0
    else:
        current_cash = 0.0
        st.error("עמודת 'מזומן_עדכני' לא נמצאה בגיליון!")

    # 5. הפרדה לפתוחות וסגורות
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # 6. נתוני לייב
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
    
    st.sidebar.write("### שווי תיק כולל")
    st.sidebar.write(f"## ${total_val:,.2f}")
    
    color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<h2 style='color:{color};'>{'+' if diff >= 0 else ''}{diff:,.2f}$</h2>", unsafe_allow_html=True)

    # --- מסך ראשי ---
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not live_list:
            st.info("אין פוזיציות פתוחות כרגע")
        else:
            st.dataframe(live_df, width=1000)
            st.divider()
            pie_data = pd.concat([pd.DataFrame(live_list), pd.DataFrame([{'Ticker': 'מזומן', 'שווי': current_cash}])])
            fig = px.pie(pie_data, values='שווי', names='Ticker', hole=0.4, title="חלוקת הון")
            st.plotly_chart(fig)

    with t2:
        if not closed_trades.empty:
            st.dataframe(closed_trades[['Ticker', 'Qty', 'Entry_Price', 'Exit_Price', 'PnL']])

except Exception as e:
    st.error(f"שגיאה קריטית בטעינה: {e}")
