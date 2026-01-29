import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון אוטומטי (10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key="final_manual_cash_v2")

# 2. הגדרות קבועות
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"
PORTFOLIO_START_VAL = 44302.55 

# 3. חיבור לנתונים
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(spreadsheet=SHEET_URL, ttl="0")
    df.columns = df.columns.str.strip()
    
    # המרת עמודות למספרים (כולל העמודה החדשה שלך)
    numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL', 'מזומן_עדכני']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- שליפת המזומן מהעמודה החדשה (N) ---
    if 'מזומן_עדכני' in df.columns:
        # לוקח את הערך האחרון שגדול מאפס בעמודה N
        cash_values = df['מזומן_עדכני'][df['מזומן_עדכני'] > 0]
        current_cash = cash_values.iloc[-1] if not cash_values.empty else 3755.0
    else:
        current_cash = 3755.0 # ברירת מחדל לביטחון

    # הפרדה לפתוחות וסגורות
    open_trades_mask = (df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")
    open_trades = df[open_trades_mask].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # נתוני לייב מהבורסה
    market_val_total = 0
    live_df = pd.DataFrame()

    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum'}).reset_index()
        tickers = list(summary['Ticker'].unique())
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        results = []
        for _, row in summary.iterrows():
            t = row['Ticker']
            price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            val = price * row['Qty']
            market_val_total += val
            results.append({'Ticker': t, 'כמות': row['Qty'], 'שווי_שוק': val})
        live_df = pd.DataFrame(results)

    # --- SIDEBAR (תצוגה חלקה) ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי (מהברוקר)", f"${current_cash:,.2f}")
    
    total_val = market_val_total + current_cash
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.write("### שווי תיק כולל")
    st.sidebar.write(f"## ${total_val:,.2f}")
    
    pnl_color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{pnl_color}; font-size: 20px; font-weight: bold;'>{'+' if diff >= 0 else ''}{diff:,.2f}$</p>", unsafe_allow_html=True)

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades.empty:
            st.dataframe(live_df.sort_values('שווי_שוק', ascending=False), use_container_width=True, hide_index=True)
            st.divider()
            # גרף פיזור תיק
            pie_data = pd.concat([live_df[['Ticker', 'שווי_שוק']].rename(columns={'שווי_שוק': 'Value'}), 
                                 pd.DataFrame([{'Ticker': 'CASH', 'Value': current_cash}])])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Ticker', hole=0.4), use_container_width=True)

    with t2:
        if not closed_trades.empty:
            realized = closed_trades['PnL'].sum()
            st.write(f"### סך רווח ממומש: ${realized:,.2f}")
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL', 'סיבת כניסה', 'סיבת יציאה']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה בעדכון הנתונים: {e}")
