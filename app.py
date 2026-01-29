import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון אוטומטי (10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key="fixed_reboot_2026")

# 2. הגדרות קבועות
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"
PORTFOLIO_START_VAL = 44302.55 

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

# 3. חיבור לנתונים
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # קריאת הנתונים מהגיליון
    df = conn.read(spreadsheet=SHEET_URL, ttl="0")
    if df is None or df.empty:
        st.error("לא הצלחתי לקרוא נתונים מהגיליון. וודא שהקישור תקין.")
        st.stop()

    df.columns = df.columns.str.strip()
    
    # המרת עמודות למספרים
    numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL', 'מזומן_עדכני']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- שליפת המזומן מעמודה N ---
    if 'מזומן_עדכני' in df.columns:
        cash_values = df['מזומן_עדכני'][df['מזומן_עדכני'] > 0]
        current_cash = float(cash_values.iloc[-1]) if not cash_values.empty else 3755.0
    else:
        current_cash = 3755.0

    # הפרדה לפתוחות וסגורות
    open_trades_mask = (df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")
    open_trades = df[open_trades_mask].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # חישוב עמלות
    total_fees = df['Qty'].apply(get_fee).sum() + closed_trades['Qty'].apply(get_fee).sum()

    # נתוני לייב
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
            val = float(price * row['Qty'])
            market_val_total += val
            avg_c = row['עלות כניסה'] / row['Qty']
            p_usd = (val - row['עלות כניסה']) - get_fee(row['Qty'])
            p_pct = ((price - avg_c) / avg_c) * 100
            results.append({'Ticker': t, 'כמות': row['Qty'], 'שווי': val, 'רווח_דולרי': p_usd, 'רווח_אחוז': p_pct})
        live_df = pd.DataFrame(results)

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${current_cash:,.2f}")
    
    total_val = market_val_total + current_cash
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.write("### שווי תיק כולל")
    st.sidebar.write(f"## ${total_val:,.2f}")
    
    pnl_color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{pnl_color}; font-size: 20px; font-weight: bold; margin-top:-10px;'>{'+' if diff >= 0 else ''}{diff:,.2f}$</p>", unsafe_allow_html=True)
    st.sidebar.write(f"עמלות מצטברות: ${total_fees:,.2f}")

    # מחשבון
    st.sidebar.divider()
    with st.sidebar.popover("🧮 מחשבון טרייד", use_container_width=True):
        c_en = st.number_input("כניסה $", value=0.0, key="c_en")
        c_st = st.number_input("סטופ $", value=0.0, key="c_st")
        if c_en > c_st:
            q = int((PORTFOLIO_START_VAL * 0.01) / (c_en - c_st))
            st.success(f"כמות: {q} | עלות: ${q*c_en:,.2f}")

    if not live_df.empty:
        st.sidebar.subheader("📈 פוזיציות (Live)")
        for _, row in live_df.iterrows():
            c = "#00c853" if row['רווח_דולרי'] >= 0 else "#ff4b4b"
            st.sidebar.write(f"**{row['Ticker']}:** ${row['שווי']:,.2f}")
            st.sidebar.markdown(f"<p style='color:{c}; margin-top:-15px;'>{'+' if row['רווח_דולרי'] >= 0 else ''}{row['רווח_דולרי']:,.2f}$</p>", unsafe_allow_html=True)

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not live_df.empty:
            st.dataframe(live_df.sort_values('שווי', ascending=False), use_container_width=True, hide_index=True)
            st.divider()
            pie_data = pd.concat([live_df[['Ticker', 'שווי']].rename(columns={'שווי': 'Value'}), 
                                 pd.DataFrame([{'Ticker': 'מזומן', 'Value': current_cash}])])
            fig = px.pie(pie_data, values='Value', names='Ticker', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
    
    with t2:
        if not closed_trades.empty:
            st.write(f"### סך רווח ממומש: ${closed_trades['PnL'].sum():,.2f}")
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה קריטית: {e}")
