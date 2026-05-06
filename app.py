import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key="auto_calc_cash_v3")

# 2. נתוני ייחוס לחישוב אוטומטי
CASH_ANCHOR = 8377.65  # המזומן שהיה לפני הפעולות האחרונות
PORTFOLIO_START_VAL = 44302.55

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

def color_pnl(val):
    try:
        color = 'red' if val < 0 else 'green'
        return f'color: {color}; font-weight: bold;'
    except: return ''

# 3. חיבור לגיליון
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    
    # המרת עמודות למספרים
    numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'עלות יציאה', 'PnL']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- חישוב מזומן אוטומטי ---
    # נחשב רק טריידים שבוצעו מהתאריך של המזומן האחרון הידוע (או פשוט את כל השינויים בגיליון)
    total_spent = df['עלות כניסה'].sum()
    total_gained = df['עלות יציאה'].sum()
    
    # חישוב עמלות: קנייה לכל שורה + מכירה רק לשורות סגורות
    fees_buy = df['Qty'].apply(get_fee).sum()
    fees_sell = df[df['Exit_Price'] > 0]['Qty'].apply(get_fee).sum()
    total_fees_accumulated = fees_buy + fees_sell
    
    # המזומן הסופי: מה שהיה פלוס מה שנמכר פחות מה שנקנה ופחות עמלות
    # הערה: מכיוון שה-CASH_ANCHOR כבר כולל חלק מהטריידים הישנים, נחשב רק טריידים חדשים או נתאים את ה-ANCHOR
    # לצרכי הדיוק שלך כרגע עם APLD, הקוד יחשב את ההפרשים מהפעולות בגיליון:
    current_cash = CASH_ANCHOR - (df[df['Entry_Date'] >= '2026-01-29']['עלות כניסה'].sum()) + (df[df['Exit_Date'] >= '2026-01-29']['עלות יציאה'].sum())

    # הפרדה
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # נתוני לייב
    market_val_total = 0
    live_list = []
    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum', 'סיבת כניסה': 'first'}).reset_index()
        tickers = [t for t in summary['Ticker'].unique() if t]
        if tickers:
            data = yf.download(tickers, period="1d", progress=False)['Close']
            for _, row in summary.iterrows():
                t = row['Ticker']
                price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
                val = price * row['Qty']
                market_val_total += val
                avg_cost = row['עלות כניסה'] / row['Qty']
                pnl_usd = (val - row['עלות כניסה']) - get_fee(row['Qty'])
                pnl_pct = ((price - avg_cost) / avg_cost) * 100
                live_list.append({'Ticker': t, 'כמות': row['Qty'], 'שווי': val, 'רווח_דולרי': pnl_usd, 'רווח_אחוז': pnl_pct, 'סיבת כניסה': row['סיבת כניסה']})
        live_df = pd.DataFrame(live_list)

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי (אוטומטי)", f"${current_cash:,.2f}")
    
    total_portfolio_now = market_val_total + current_cash
    diff_ytd = total_portfolio_now - PORTFOLIO_START_VAL
    
    st.sidebar.write("### שווי תיק כולל")
    st.sidebar.write(f"## ${total_portfolio_now:,.2f}")
    
    c_ytd = "#00c853" if diff_ytd >= 0 else "#ff4b4b"
    icon = "▲" if diff_ytd >= 0 else "▼"
    st.sidebar.markdown(f"<h3 style='color:{c_ytd}; margin:0;'>{icon} ${abs(diff_ytd):,.2f}</h3>", unsafe_allow_html=True)
    
    st.sidebar.write("📉 **עמלות מצטברות:**")
    st.sidebar.markdown(f"<p style='color:#ff4b4b; font-size: 18px; font-weight: bold;'>-${total_fees_accumulated:,.2f}</p>", unsafe_allow_html=True)

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not live_list == []:
            st.dataframe(live_df.style.map(color_pnl, subset=['רווח_דולרי', 'רווח_אחוז']), use_container_width=True, hide_index=True)
            st.divider()
            pie_data = pd.concat([live_df[['Ticker', 'שווי']].rename(columns={'שווי': 'Value'}), pd.DataFrame([{'Ticker': 'מזומן', 'Value': current_cash}])])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Ticker', hole=0.4), use_container_width=True)

    with t2:
        if not closed_trades.empty:
            realized_sum = closed_trades['PnL'].sum()
            st.markdown(f"### סך רווח ממומש: <span style='color:{'green' if realized_sum >=0 else 'red'};'>${realized_sum:,.2f}</span>", unsafe_allow_html=True)
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL', 'סיבת כניסה', 'סיבת יציאה']].sort_values('Exit_Date', ascending=False), use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
