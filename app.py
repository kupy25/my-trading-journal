import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון אוטומטי (10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key="broker_sync_fix")

# 2. נתוני ייחוס מדויקים לפי הברוקר (נכון ל-06/05/2026)
# עדכנתי את העוגן לפי הנתונים שסיפקת כדי לאפס את החישוב
CASH_ANCHOR = 2429.45  
PORTFOLIO_START_VAL = 44302.55 

def get_fee(qty):
    # $3.50 + עמלות משתנות של $0.0078 למניה
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

    # --- חישוב מזומן דינמי ---
    # הקוד מחשב שינויים רק עבור טריידים חדשים שנוספו מהיום והלאה
    # כדי לשמור על סנכרון עם ה-CASH_ANCHOR שסיפקת
    new_activity = df[df['Entry_Date'] > '2026-05-06']
    new_exits = df[df['Exit_Date'] > '2026-05-06']
    
    cash_spent = new_activity['עלות כניסה'].sum()
    cash_gained = new_exits['עלות יציאה'].sum()
    fees_new = new_activity['Qty'].apply(get_fee).sum() + new_exits['Qty'].apply(get_fee).sum()
    
    # המזומן המעודכן
    dynamic_cash = CASH_ANCHOR - cash_spent + cash_gained - fees_new

    # עמלות מצטברות לכל התיק (לתצוגה)
    total_fees_ytd = df['Qty'].apply(get_fee).sum() + df[df['Exit_Price'] > 0]['Qty'].apply(get_fee).sum()

    # הפרדה לפוזיציות
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Qty'] > 0)].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    market_val_total = 0
    live_list = []
    
    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum', 'סיבת כניסה': 'first'}).reset_index()
        tickers = [t for t in summary['Ticker'].unique() if t]
        
        if tickers:
            data = yf.download(tickers, period="1d", progress=False)['Close']
            for _, row in summary.iterrows():
                t = row['Ticker']
                try:
                    price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
                    val = price * row['Qty']
                    market_val_total += val
                    avg_cost = row['עלות כניסה'] / row['Qty']
                    pnl_usd = (val - row['עלות כניסה']) - get_fee(row['Qty'])
                    pnl_pct = ((price - avg_cost) / avg_cost) * 100
                    live_list.append({'Ticker': t, 'כמות': row['Qty'], 'שווי': val, 'רווח_דולרי': pnl_usd, 'רווח_אחוז': pnl_pct, 'סיבת כניסה': row['סיבת כניסה']})
                except: continue
        live_df = pd.DataFrame(live_list)

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${dynamic_cash:,.2f}")
    
    total_portfolio_now = market_val_total + dynamic_cash
    diff_ytd = total_portfolio_now - PORTFOLIO_START_VAL
    
    st.sidebar.write("### שווי תיק כולל")
    st.sidebar.write(f"## ${total_portfolio_now:,.2f}")
    
    c_ytd = "#00c853" if diff_ytd >= 0 else "#ff4b4b"
    icon = "▲" if diff_ytd >= 0 else "▼"
    st.sidebar.markdown(f"<h3 style='color:{c_ytd}; margin:0;'>{icon} ${abs(diff_ytd):,.2f}</h3>", unsafe_allow_html=True)
    
    st.sidebar.write("📉 **עמלות מצטברות:**")
    st.sidebar.markdown(f"<p style='color:#ff4b4b; font-size: 18px; font-weight: bold;'>-${total_fees_ytd:,.2f}</p>", unsafe_allow_html=True)

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    st.link_button("📂 פתח גוגל שיט", "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit")

    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not live_list == []:
            st.dataframe(live_df.style.map(color_pnl, subset=['רווח_דולרי', 'רווח_אחוז']), use_container_width=True, hide_index=True)
            st.divider()
            st.subheader("🥧 התפלגות תיק")
            pie_data = pd.concat([live_df[['Ticker', 'שווי']].rename(columns={'שווי': 'Value'}), pd.DataFrame([{'Ticker': 'מזומן', 'Value': dynamic_cash}])])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Ticker', hole=0.4), use_container_width=True)

    with t2:
        if not closed_trades.empty:
            realized_sum = closed_trades['PnL'].sum()
            st.markdown(f"### סך רווח ממומש: <span style='color:{'green' if realized_sum >=0 else 'red'};'>${realized_sum:,.2f}</span>", unsafe_allow_html=True)
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL', 'סיבת כניסה', 'סיבת יציאה']].sort_values('Exit_Date', ascending=False), use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
