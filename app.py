import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import time

# 1. הגדרות דף ורענון (10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key=f"fixed_reboot_{int(time.time())}")

# 2. הקישור הישיר שלך (CSV)
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQKaG_u8xiC5wYWL3QihjRCsS8FA1O3hjvIWnCwmh3k4yPOK_5scHuwlURvHZjwj3Zo3QWEMse_pK5i/pub?output=csv"
PORTFOLIO_START_VAL = 44302.55 

try:
    # 3. קריאת נתונים עם עוקף מטמון
    df = pd.read_csv(f"{CSV_URL}&cache={int(time.time())}")
    df.columns = df.columns.str.strip()
    
    # המרת עמודות למספרים
    numeric_cols = ['Qty', 'עלות כניסה', 'Exit_Price', 'PnL', 'מזומן_עדכני']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- משיכת מזומן מתא N2 (הערך הראשון בעמודה מזומן_עדכני) ---
    if 'מזומן_עדכני' in df.columns:
        current_cash = float(df['מזומן_עדכני'].iloc[0])
    else:
        current_cash = 8377.65 # ערך גיבוי למקרה של תקלה

    # 4. סינון פוזיציות פתוחות (Ticker קיים ו-Exit_Price הוא 0)
    # לפי הגיליון שלך: BITB, MSTR, ETHA פתוחות (Exit_Price ריק/0)
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # 5. נתוני לייב
    market_val_total = 0
    live_list = []

    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum'}).reset_index()
        tickers = summary['Ticker'].unique().tolist()
        
        # הורדת נתונים מ-Yahoo Finance
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        for _, row in summary.iterrows():
            t = row['Ticker']
            price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            val = float(price * row['Qty'])
            market_val_total += val
            
            p_usd = val - row['עלות כניסה']
            p_pct = ((price - (row['עלות כניסה']/row['Qty'])) / (row['עלות כניסה']/row['Qty'])) * 100
            live_list.append({'Ticker': t, 'שווי': val, 'רווח_$': p_usd, 'רווח_%': p_pct})
        
        live_df = pd.DataFrame(live_list)

    # --- SIDEBAR (החזרת התצוגה שעובדת) ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי (N2)", f"${current_cash:,.2f}")
    
    total_val = market_val_total + current_cash
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.write("### שווי תיק כולל")
    st.sidebar.write(f"## ${total_val:,.2f}")
    
    p_color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<h3 style='color:{p_color};'>{'+' if diff >= 0 else ''}{diff:,.2f}$</h3>", unsafe_allow_html=True)

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades.empty:
            st.dataframe(live_df.sort_values('שווי', ascending=False), use_container_width=True, hide_index=True)
            st.divider()
            # גרף פיזור הון
            pie_data = pd.concat([live_df[['Ticker', 'שווי']].rename(columns={'שווי': 'Value'}), 
                                 pd.DataFrame([{'Ticker': 'CASH', 'Value': current_cash}])])
            fig = px.pie(pie_data, values='Value', names='Ticker', hole=0.4, title="פיזור הון בתיק")
            st.plotly_chart(fig, use_container_width=True)

    with t2:
        if not closed_trades.empty:
            st.write(f"### סך רווח ממומש: ${closed_trades['PnL'].sum():,.2f}")
            st.dataframe(closed_trades[['Ticker', 'Qty', 'Entry_Price', 'Exit_Price', 'PnL']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה בחיבור: {e}")
