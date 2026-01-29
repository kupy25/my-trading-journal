import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import time

# 1. הגדרות דף ורענון (10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key=f"clean_reboot_{int(time.time())}")

# 2. הקישור הישיר שלך (CSV)
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQKaG_u8xiC5wYWL3QihjRCsS8FA1O3hjvIWnCwmh3k4yPOK_5scHuwlURvHZjwj3Zo3QWEMse_pK5i/pub?output=csv"
PORTFOLIO_START_VAL = 44302.55 

try:
    # 3. קריאת נתונים עם עוקף מטמון (Cache Buster)
    # הוספת timestamp ייחודי לכל קריאה כדי להכריח את גוגל לשלוח נתונים חדשים
    df = pd.read_csv(f"{CSV_URL}&nocache={int(time.time())}")
    df.columns = df.columns.str.strip()
    
    # ניקוי והמרת עמודות למספרים (בדיוק לפי השמות בגיליון שלך)
    numeric_cols = ['Qty', 'עלות כניסה', 'Exit_Price', 'PnL', 'מזומן_עדכני']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 4. משיכת מזומן: לוקח את הערך הראשון בעמודה N (תא N2)
    # הסרתי כל מספר "קפוא" שהיה כאן קודם.
    if 'מזומן_עדכני' in df.columns:
        current_cash = float(df['מזומן_עדכני'].iloc[0])
    else:
        current_cash = 0.0
        st.sidebar.error("עמודת 'מזומן_עדכני' לא נמצאה בגיליון!")

    # 5. סינון פוזיציות: פתוח = אין מחיר יציאה
    # זה יוודא ש-ONDS ו-RCAT לא ינפחו את השווי אם עדכנת להן Exit_Price
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # 6. נתוני לייב (BITB, MSTR, ETHA)
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

    # --- SIDEBAR (ניהול חשבון) ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${current_cash:,.2f}")
    
    total_val = market_val_total + current_cash
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.write("### שווי תיק כולל")
    st.sidebar.write(f"## ${total_val:,.2f}")
    
    color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<h3 style='color:{color};'>{'+' if diff >= 0 else ''}{diff:,.2f}$</h3>", unsafe_allow_html=True)

    # פירוט פוזיציות ב-Sidebar
    if not live_df.empty:
        st.sidebar.divider()
        st.sidebar.subheader("📈 פוזיציות לייב")
        for _, row in live_df.iterrows():
            st.sidebar.write(f"**{row['Ticker']}:** ${row['שווי']:,.2f}")

    # --- מסך ראשי ---
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades.empty:
            st.dataframe(live_df, use_container_width=True, hide_index=True)
            st.divider()
            # גרף פאי
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
