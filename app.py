import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import time

# 1. הגדרות דף ורענון (10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key="final_verified_refresh_v3")

# 2. הקישור הישיר שלך (כולל מנגנון עקיפת מטמון)
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQKaG_u8xiC5wYWL3QihjRCsS8FA1O3hjvIWnCwmh3k4yPOK_5scHuwlURvHZjwj3Zo3QWEMse_pK5i/pub?output=csv"
PORTFOLIO_START_VAL = 44302.55 

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

try:
    # 3. קריאה ישירה של הנתונים מהקישור ששלחת
    # הוספת timestamp לקישור כדי להכריח את גוגל לשלוח נתונים טריים
    df = pd.read_csv(f"{CSV_URL}&t={int(time.time())}")
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

    # 5. הפרדה לפתוחות וסגורות
    open_trades_mask = (df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")
    open_trades = df[open_trades_mask].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # חישוב עמלות מצטברות (קנייה לכולם + מכירה לסגורים)
    total_fees = df['Qty'].apply(get_fee).sum() + closed_trades['Qty'].apply(get_fee).sum()

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
            
            avg_cost = row['עלות כניסה'] / row['Qty']
            pnl_usd = (val - row['עלות כניסה']) - get_fee(row['Qty'])
            pnl_pct = ((price - avg_cost) / avg_cost) * 100
            live_list.append({'Ticker': t, 'שווי': val, 'רווח_$': pnl_usd, 'רווח_%': pnl_pct})
        
        live_df = pd.DataFrame(live_list)

    # --- SIDEBAR (החזרת כל המרכיבים) ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${current_cash:,.2f}")
    
    total_val = market_val_total + current_cash
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.write("### שווי תיק כולל")
    st.sidebar.write(f"## ${total_val:,.2f}")
    
    color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<h2 style='color:{color};'>{'+' if diff >= 0 else ''}{diff:,.2f}$</h2>", unsafe_allow_html=True)
    st.sidebar.write(f"📉 עמלות מצטברות: ${total_fees:,.2f}")

    # מחשבון טרייד
    st.sidebar.divider()
    with st.sidebar.popover("🧮 מחשבון טרייד", use_container_width=True):
        c_en = st.number_input("כניסה $", value=0.0, key="en_val")
        c_st = st.number_input("סטופ $", value=0.0, key="st_val")
        if c_en > c_st:
            q = int((PORTFOLIO_START_VAL * 0.01) / (c_en - c_st))
            st.success(f"כמות: {q} | עלות: ${q*c_en:,.2f}")

    # פירוט פוזיציות בסיידבר
    if not open_trades.empty:
        st.sidebar.subheader("📈 פוזיציות פתוחות")
        for _, row in live_df.iterrows():
            p_c = "#00c853" if row['רווח_$'] >= 0 else "#ff4b4b"
            st.sidebar.write(f"**{row['Ticker']}:** ${row['שווי']:,.2f}")
            st.sidebar.markdown(f"<p style='color:{p_c}; margin-top:-15px;'>{row['רווח_$']:,.2f}$ ({row['רווח_%']:.2f}%)</p>", unsafe_allow_html=True)

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades.empty:
            st.dataframe(live_df.sort_values('שווי', ascending=False), use_container_width=True, hide_index=True)
            st.divider()
            # גרף פאי
            pie_data = pd.concat([live_df[['Ticker', 'שווי']].rename(columns={'שווי': 'Value'}), 
                                 pd.DataFrame([{'Ticker': 'CASH', 'Value': current_cash}])])
            fig = px.pie(pie_data, values='Value', names='Ticker', hole=0.4, title="פיזור הון")
            st.plotly_chart(fig, use_container_width=True)

    with t2:
        if not closed_trades.empty:
            st.write(f"### סך רווח ממומש: ${closed_trades['PnL'].sum():,.2f}")
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL', 'סיבת כניסה']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה בטעינת הנתונים: {e}")
