import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=15000, key="datarefresh")

# --- הגדרות מזומן מדויקות ---
CASH_BASIS = 9535.30  # המזומן שהיה לך בברוקר לפני הטרייד האחרון
# כאן תרשום את הטיקרים שהיו פתוחים כבר כשהיו לך 9535 דולר (כדי שהקוד לא יחסיר אותם שוב)
ALREADY_OPEN_TICKERS = ['BITB', 'CIFR', 'CRML', 'MSTR'] 

PORTFOLIO_START_VAL = 44302.55 
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

# 2. חיבור וקריאת נתונים
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    
    numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # הפרדה לפוזיציות
    open_trades_raw = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    
    # --- חישוב מזומן דינמי מתוקן ---
    # אנחנו מחסירים מהמזומן רק פוזיציות שהן חדשות (לא היו ברשימת הבסיס)
    new_trades = open_trades_raw[~open_trades_raw['Ticker'].isin(ALREADY_OPEN_TICKERS)]
    cost_of_new_trades = new_trades['עלות כניסה'].sum()
    
    current_cash_dynamic = CASH_BASIS - cost_of_new_trades

    market_val_total = 0
    live_list = []

    if not open_trades_raw.empty:
        summary = open_trades_raw.groupby('Ticker').agg({
            'Qty': 'sum', 
            'עלות כניסה': 'sum',
            'סיבת כניסה': 'first'
        }).reset_index()
        
        tickers = list(summary['Ticker'].unique())
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        for _, row in summary.iterrows():
            t = row['Ticker']
            try:
                price = data[t].dropna().iloc[-1] if len(tickers) > 1 else data.dropna().iloc[-1]
                qty = row['Qty']
                total_cost = row['עלות כניסה']
                val = price * qty
                market_val_total += val
                
                avg_price = total_cost / qty if qty != 0 else 0
                pnl_usd = (val - total_cost) - get_fee(qty)
                pnl_pct = ((price - avg_price) / avg_price) * 100 if avg_price != 0 else 0
                
                live_list.append({
                    'Ticker': t, 'כמות': qty, 'מחיר ממוצע': avg_price,
                    'מחיר שוק': price, 'שווי פוזיציה': val, 'רווח $': pnl_usd, 
                    'רווח %': pnl_pct, 'סיבת כניסה': row['סיבת כניסה']
                })
            except: continue
        
        live_df = pd.DataFrame(live_list)

    # --- חישוב שווי כולל ---
    total_portfolio_live = current_cash_dynamic + market_val_total
    diff_from_start = total_portfolio_live - PORTFOLIO_START_VAL

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי (מעודכן)", f"${current_cash_dynamic:,.2f}")
    st.sidebar.metric("שווי מניות (Live)", f"${market_val_total:,.2f}")
    
    st.sidebar.divider()
    st.sidebar.write("### שווי תיק כולל (Live)")
    st.sidebar.write(f"## ${total_portfolio_live:,.2f}")
    
    color = "#00c853" if diff_from_start >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{color}; font-size: 20px; font-weight: bold; margin-top:-10px;'>{'+' if diff_from_start >= 0 else ''}{diff_from_start:,.2f}$</p>", unsafe_allow_html=True)

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if live_list:
            def format_pnl(val): return f'color: {"green" if val > 0 else "red"}'
            st.dataframe(live_df.style.map(format_pnl, subset=['רווח $', 'רווח %'])\
                         .format({'מחיר ממוצע': "{:.2f}$", 'מחיר שוק': "{:.2f}$", 'שווי פוזיציה': "{:,.2f}$", 'רווח $': "{:,.2f}$", 'רווח %': "{:.2f}%"}), 
                         use_container_width=True, hide_index=True)
            
            st.divider()
            pie_data = pd.concat([live_df[['Ticker', 'שווי פוזיציה']].rename(columns={'שווי פוזיציה': 'Value'}), 
                                 pd.DataFrame([{'Ticker': 'מזומן', 'Value': current_cash_dynamic}])])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Ticker', hole=0.4, title="פיזור תיק"), use_container_width=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
