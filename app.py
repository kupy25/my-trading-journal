import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import time

# 1. הגדרות דף ורענון (10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key=f"reboot_final_{int(time.time())}")

# 2. שינוי מבנה הקישור לקישור ישיר (Export) שעוקף את ה-Cache של גוגל
# זה הקישור המקורי שלך מותאם להורדה ישירה
SHEET_ID = "11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg"
DIRECT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

PORTFOLIO_START_VAL = 44302.55 

try:
    # 3. קריאה ישירה עם מנגנון מניעת Cache אגרסיבי
    t_stamp = int(time.time())
    df = pd.read_csv(f"{DIRECT_URL}&cachebuster={t_stamp}")
    df.columns = df.columns.str.strip()
    
    # המרת עמודות למספרים (בדיוק לפי השמות בגיליון שלך)
    numeric_cols = ['Qty', 'עלות כניסה', 'Exit_Price', 'PnL', 'מזומן_עדכני']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 4. שליפת המזומן מעמודה N (תא N2)
    # אין כאן אף מספר קבוע - הכל מגיע מהגיליון
    if 'מזומן_עדכני' in df.columns:
        current_cash = float(df['מזומן_עדכני'].iloc[0])
    else:
        current_cash = 0.0

    # 5. סינון פוזיציות (פוזיציה סגורה = Exit_Price גדול מ-0)
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # 6. נתוני לייב
    market_val_total = 0
    live_df = pd.DataFrame()

    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum'}).reset_index()
        tickers = summary['Ticker'].tolist()
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        results = []
        for _, row in summary.iterrows():
            t = row['Ticker']
            price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            val = float(price * row['Qty'])
            market_val_total += val
            
            p_usd = val - row['עלות כניסה']
            p_pct = ((price - (row['עלות כניסה']/row['Qty'])) / (row['עלות כניסה']/row['Qty'])) * 100
            results.append({'Ticker': t, 'שווי': val, 'רווח_$': p_usd, 'רווח_%': p_pct})
        live_df = pd.DataFrame(results)

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    # הצגת המזומן - אם זה עדיין 3755, סימן שגוגל שולח קובץ ישן
    st.sidebar.metric("מזומן פנוי", f"${current_cash:,.2f}")
    
    total_val = market_val_total + current_cash
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.write("### שווי תיק כולל")
    st.sidebar.write(f"## ${total_val:,.2f}")
    
    color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<h3 style='color:{color};'>{'+' if diff >= 0 else ''}{diff:,.2f}$</h3>", unsafe_allow_html=True)

    # --- מסך ראשי ---
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades.empty:
            st.dataframe(live_df, use_container_width=True, hide_index=True)
            st.divider()
            pie_data = pd.concat([live_df[['Ticker', 'שווי']].rename(columns={'שווי': 'Value'}), 
                                 pd.DataFrame([{'Ticker': 'CASH', 'Value': current_cash}])])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Ticker', hole=0.4), use_container_width=True)
        else:
            st.info("אין פוזיציות פתוחות.")

    with t2:
        if not closed_trades.empty:
            st.write(f"### רווח ממומש: ${closed_trades['PnL'].sum():,.2f}")
            st.dataframe(closed_trades[['Ticker', 'Qty', 'PnL', 'Exit_Price']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה קריטית: {e}")
