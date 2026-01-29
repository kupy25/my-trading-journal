import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import time

# 1. הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key=f"reboot_v9_{int(time.time())}")

# 2. הגדרת קישורים (החלפתי לקישור הישיר שלך)
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit#gid=0"
CSV_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/export?format=csv&gid=0"

# הצגת הקישור בראש הדף כדי לוודא שהקוד התעדכן
st.markdown(f"### [🔗 לחץ כאן למעבר לגוגל שיטס]({SHEET_URL})")
st.divider()

try:
    # 3. קריאה ישירה ללא "מספרי רפאים"
    # הוספת Timestamp כדי להכריח את גוגל לשלוח נתונים טריים
    df = pd.read_csv(f"{CSV_URL}&t={int(time.time())}")
    df.columns = df.columns.str.strip()
    
    # ניקוי עמודות
    for col in ['Qty', 'עלות כניסה', 'Exit_Price', 'PnL', 'מזומן_עדכני']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 4. משיכת מזומן מעמודה N (תא N2)
    # שים לב: אין כאן אף מספר ידני!
    if 'מזומן_עדכני' in df.columns:
        current_cash = float(df['מזומן_עדכני'].iloc[0])
    else:
        current_cash = 0.0

    # 5. סינון פוזיציות
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # 6. נתוני לייב
    market_val_total = 0
    live_list = []
    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum'}).reset_index()
        tickers = summary['Ticker'].tolist()
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
    st.sidebar.subheader("שווי תיק כולל")
    st.sidebar.title(f"${total_val:,.2f}")

    # --- טאבים ---
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    with t1:
        if not open_trades.empty:
            st.dataframe(live_df, use_container_width=True, hide_index=True)
            st.plotly_chart(px.pie(pd.concat([live_df, pd.DataFrame([{'Ticker': 'מזומן', 'שווי': current_cash}])]), 
                                  values='שווי', names='Ticker', hole=0.4), use_container_width=True)

    with t2:
        st.dataframe(closed_trades[['Ticker', 'Qty', 'PnL']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה בחיבור: {e}")
