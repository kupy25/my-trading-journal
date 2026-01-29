import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import time

# 1. הגדרות דף ורענון (10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key=f"force_refresh_{int(time.time())}")

# 2. הקישור הישיר שלך
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQKaG_u8xiC5wYWL3QihjRCsS8FA1O3hjvIWnCwmh3k4yPOK_5scHuwlURvHZjwj3Zo3QWEMse_pK5i/pub?output=csv"
PORTFOLIO_START_VAL = 44302.55 

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

try:
    # 3. קריאת הנתונים עם עוקף מטמון (כדי לראות שינויים מיד)
    df = pd.read_csv(f"{CSV_URL}&cache={int(time.time())}")
    df.columns = df.columns.str.strip()
    
    # ניקוי נתונים
    for col in ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL', 'מזומן_עדכני']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- משיכת מזומן מתא N2 בלבד ---
    # זה מבטיח שאם רשמת את המזומן בראש העמודה, הקוד תמיד יראה אותו
    if 'מזומן_עדכני' in df.columns:
        # לוקח את הערך הראשון בעמודה N (שנמצא בשורה N2 בגיליון)
        current_cash = float(df['מזומן_עדכני'].iloc[0]) 
    else:
        current_cash = 0.0

    # 4. הפרדה לפתוחות וסגורות
    # פתוח = אין מחיר יציאה
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # 5. נתוני לייב מ-Yahoo Finance
    market_val_total = 0
    live_list = []

    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum'}).reset_index()
        tickers = list(summary['Ticker'].unique())
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        for _, row in summary.iterrows():
            t = row['Ticker']
            # טיפול במקרה של מניה בודדת או כמה מניות
            price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            val = float(price * row['Qty'])
            market_val_total += val
            
            avg_cost = row['עלות כניסה'] / row['Qty']
            pnl_usd = (val - row['עלות כניסה']) - (get_fee(row['Qty']) * 2)
            pnl_pct = ((price - avg_cost) / avg_cost) * 100
            live_list.append({'Ticker': t, 'שווי': val, 'רווח_$': pnl_usd, 'רווח_%': pnl_pct})
        
        live_df = pd.DataFrame(live_list)

    # --- תצוגת SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי (מתא N2)", f"${current_cash:,.2f}")
    
    total_portfolio_val = market_val_total + current_cash
    profit_loss = total_portfolio_val - PORTFOLIO_START_VAL
    
    st.sidebar.write("### שווי תיק כולל")
    st.sidebar.write(f"## ${total_portfolio_val:,.2f}")
    
    color = "#00c853" if profit_loss >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<h3 style='color:{color};'>{'+' if profit_loss >= 0 else ''}{profit_loss:,.2f}$</h3>", unsafe_allow_html=True)

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
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
            st.info("אין פוזיציות פתוחות. כל ההון במזומן.")

    with t2:
        if not closed_trades.empty:
            st.write(f"### סך רווח ממומש: ${closed_trades['PnL'].sum():,.2f}")
            st.dataframe(closed_trades[['Ticker', 'Qty', 'PnL', 'Entry_Date', 'Exit_Date']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה בטעינת הנתונים: {e}")
