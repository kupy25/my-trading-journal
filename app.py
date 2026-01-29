import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key="direct_gsheets_sync")

# 2. חיבור ישיר לגיליון (עוקף את ה-CSV האיטי)
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # קריאת הנתונים - ttl=0 מבטיח שאין זיכרון מטמון בכלל
    df = conn.read(ttl=0)
    df.columns = df.columns.str.strip()
    
    # המרת עמודות למספרים
    numeric_cols = ['Qty', 'עלות כניסה', 'Exit_Price', 'PnL', 'מזומן_עדכני']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- משיכת המזומן מעמודה N ---
    # לוקח את הערך הראשון (תא N2) כפי שמופיע בגיליון שלך
    if 'מזומן_עדכני' in df.columns:
        current_cash = float(df['מזומן_עדכני'].iloc[0])
    else:
        current_cash = 8377.65

    # 3. סינון פוזיציות
    # ONDS ו-RCAT יוסרו אוטומטית כי יש להן Exit_Price בגיליון
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # 4. נתוני לייב (BITB, MSTR, ETHA)
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
            results.append({'Ticker': t, 'שווי': val, 'PnL_$': val - row['עלות כניסה']})
        live_df = pd.DataFrame(results)

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${current_cash:,.2f}")
    
    total_val = market_val_total + current_cash
    st.sidebar.write(f"### שווי תיק כולל: ${total_val:,.2f}")

    # --- תצוגה ראשית ---
    st.title("📊 יומן המסחר של אבי")
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades.empty:
            st.dataframe(live_df, use_container_width=True, hide_index=True)
            st.divider()
            pie_data = pd.concat([live_df[['Ticker', 'שווי']].rename(columns={'שווי': 'Value'}), 
                                 pd.DataFrame([{'Ticker': 'CASH', 'Value': current_cash}])])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Ticker', hole=0.4), use_container_width=True)

    with t2:
        if not closed_trades.empty:
            st.write(f"### רווח ממומש: ${closed_trades['PnL'].sum():,.2f}")
            st.dataframe(closed_trades[['Ticker', 'Qty', 'PnL']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה בחיבור ישיר: {e}")
