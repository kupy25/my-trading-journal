import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון אוטומטי
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=15000, key="datarefresh")

# --- הגדרות יסוד ---
PORTFOLIO_START_VAL = 44302.55  # שווי התיק ביום פתיחת היומן
CASH_AT_START = 12298.89       # המזומן שהיה פנוי ביום פתיחת היומן
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

# 2. חיבור וקריאת נתונים
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    
    # ניקוי עמודות נומריות
    numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- חישוב מזומן פנוי דינמי ---
    # 1. רווח/הפסד מטריידים סגורים (כבר כולל את החזר הקרן + הרווח)
    realized_pnl = df[df['Exit_Price'] > 0]['PnL'].sum()
    
    # 2. כסף שמושקע כרגע בפוזיציות פתוחות
    open_trades_mask = (df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")
    money_in_open_positions = df[open_trades_mask]['עלות כניסה'].sum()
    
    # המזומן הנוכחי = מזומן התחלתי + רווחים ממומשים - כסף שנעול כרגע במניות
    current_cash = CASH_AT_START + realized_pnl - money_in_open_positions

    # מיון פוזיציות לתצוגה
    open_trades = df[open_trades_mask].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # חישוב שווי שוק לייב (Live Market Value)
    market_val_total = 0
    live_list = []

    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({
            'Qty': 'sum', 
            'עלות כניסה': 'sum',
            'סיבת כניסה': 'first'
        }).reset_index()
        
        tickers = list(summary['Ticker'].unique())
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        for _, row in summary.iterrows():
            t = row['Ticker']
            try:
                # טיפול במקרה של טיקר יחיד או מרובים ב-yfinance
                if len(tickers) > 1:
                    price = data[t].dropna().iloc[-1]
                else:
                    price = data.dropna().iloc[-1]
                    
                val = price * row['Qty']
                market_val_total += val
                
                avg_cost = row['עלות כניסה'] / row['Qty'] if row['Qty'] != 0 else 0
                pnl_usd = (val - row['עלות כניסה']) - get_fee(row['Qty'])
                pnl_pct = ((price - avg_cost) / avg_cost) * 100 if avg_cost != 0 else 0
                
                live_list.append({
                    'Ticker': t, 'כמות': row['Qty'], 'שווי': val, 
                    'רווח $': pnl_usd, 'רווח %': pnl_pct, 'סיבת כניסה': row['סיבת כניסה']
                })
            except: continue
        
        live_df = pd.DataFrame(live_list)

    # --- SIDEBAR (חישובי שווי כולל) ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי (מחושב)", f"${current_cash:,.2f}")
    
    # שווי התיק = מזומן פנוי + שווי שוק נוכחי של המניות
    total_portfolio_val = market_val_total + current_cash
    diff_from_start = total_portfolio_val - PORTFOLIO_START_VAL
    
    st.sidebar.write("### שווי תיק כולל (Live)")
    st.sidebar.write(f"## ${total_portfolio_val:,.2f}")
    
    color = "#00c853" if diff_from_start >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{color}; font-size: 20px; font-weight: bold; margin-top:-10px;'>{'+' if diff_from_start >= 0 else ''}{diff_from_start:,.2f}$</p>", unsafe_allow_html=True)
    
    # מחשבון טרייד
    st.sidebar.divider()
    st.sidebar.subheader("🧮 מחשבון טרייד")
    calc_ticker = st.sidebar.text_input("סימול מניה", value="AAPL")
    c_entry = st.sidebar.number_input("מחיר כניסה $", value=0.0)
    c_stop = st.sidebar.number_input("מחיר סטופ $", value=0.0)
    
    if c_entry > c_stop and c_stop > 0:
        risk_amount = PORTFOLIO_START_VAL * 0.01 # סיכון של 1% מהתיק
        q = int(risk_amount / (c_entry - c_stop))
        st.sidebar.success(f"מניה: {calc_ticker}\n\nכמות: {q} יח'\n\nעלות: ${q*c_entry:,.2f}")

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    st.link_button("📂 פתח את גיליון הגוגל שיטס", SHEET_URL)

    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades.empty and not live_df.empty:
            def color_pnl(val):
                return f'color: {"green" if val > 0 else "red"}'
            styled_df = live_df.style.map(color_pnl, subset=['רווח $', 'רווח %'])\
                                     .format({'שווי': "{:,.2f}$", 'רווח $': "{:,.2f}$", 'רווח %': "{:.2f}%"})
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            st.divider()
            pie_data = pd.concat([live_df[['Ticker', 'שווי']].rename(columns={'שווי': 'Value'}), 
                                 pd.DataFrame([{'Ticker': 'מזומן', 'Value': current_cash}])])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Ticker', hole=0.4, title="פיזור תיק ריאלי (מזומן נגד מניות)"), use_container_width=True)

    with t2:
        if not closed_trades.empty:
            st.metric("סך רווח ממומש", f"${realized_pnl:,.2f}")
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL', 'סיבת כניסה']].sort_values('Exit_Date', ascending=False), 
                         use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה בעיבוד הנתונים: {e}")
