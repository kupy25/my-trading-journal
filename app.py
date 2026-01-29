import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")

# רענון בטוח לענן
st_autorefresh(interval=10000, key="dynamic_cash_refresh")

# --- הזרקת CSS ליישור לימין ---
st.markdown("""
    <style>
    h1, h2, h3, [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
        text-align: right; direction: rtl;
    }
    button[data-baseweb="tab"] { direction: rtl; }
    </style>
    """, unsafe_allow_html=True)

SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

# --- הגדרות בסיס ---
CASH_REFERENCE = 4957.18  # המזומן שהיה בתיק בנקודת ההתחלה של היומן
initial_portfolio_value = 44302.55

def calculate_trade_fee(qty):
    return 3.50 + (qty * (0.0048 + 0.003)) if qty > 0 else 0

conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    
    for col in ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # 1. חישוב המזומן הדינמי:
    # לוקחים את הייחוס ומורידים ממנו את כל הכסף שהושקע בפוזיציות פתוחות + עמלות עליהן
    open_positions_mask = (df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")
    raw_open = df[open_positions_mask].copy()
    
    total_invested_now = raw_open['עלות כניסה'].sum()
    total_open_fees = raw_open['Qty'].apply(calculate_trade_fee).sum()
    
    # המזומן הנוכחי = הייחוס פחות מה שקנית מאז
    current_cash = CASH_REFERENCE - total_invested_now - total_open_fees

    # 2. חישוב עמלות כולל (פתוחות וסגורות)
    closed_trades = df[df['Exit_Price'] > 0].copy()
    fees_closed = (closed_trades['Qty'].apply(calculate_trade_fee).sum() * 2) # קנייה ומכירה
    total_fees_display = total_open_fees + fees_closed

    # 3. עיבוד פוזיציות לתצוגה
    market_val_total = 0
    open_trades_display = pd.DataFrame()
    if not raw_open.empty:
        open_trades_display = raw_open.groupby('Ticker').agg({
            'Qty': 'sum', 'עלות כניסה': 'sum', 'Entry_Date': 'min',
            'סיבת כניסה': lambda x: " | ".join(set(x.dropna().astype(str)))
        }).reset_index()
        
        tickers = list(open_trades_display['Ticker'].unique())
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        live_list = []
        for _, row in open_trades_display.iterrows():
            t = row['Ticker']
            curr = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            val = curr * row['Qty']
            market_val_total += val
            
            entry_p = row['עלות כניסה'] / row['Qty']
            pnl_usd = (val - row['עלות כניסה']) - calculate_trade_fee(row['Qty'])
            pnl_pct = ((curr - entry_p) / entry_p) * 100
            live_list.append({'Ticker': t, 'Market_Value': val, 'PnL_Net': pnl_usd, 'PnL_Pct': pnl_pct})
        
        open_trades_display = open_trades_display.merge(pd.DataFrame(live_list), on='Ticker')

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${current_cash:,.2f}")
    
    total_portfolio = market_val_total + current_cash
    diff = total_portfolio - initial_portfolio_value
    
    st.sidebar.write(f"### שווי תיק כולל")
    st.sidebar.write(f"## ${total_portfolio:,.2f}")
    diff_color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{diff_color}; font-size: 20px; font-weight: bold; margin-top:-10px; text-align:right;'>{'+' if diff >= 0 else ''}{diff:,.2f}$</p>", unsafe_allow_html=True)
    
    st.sidebar.write("📉 **עלויות מסחר מצטברות:**")
    st.sidebar.markdown(f"<p style='color:#ff4b4b; font-size: 18px; font-weight: bold; margin-top:-10px; text-align:right;'>-${total_fees_display:,.2f}</p>", unsafe_allow_html=True)

    # ... שאר הקוד (טאבים, טבלאות) ...
    st.sidebar.divider()
    if not open_trades_display.empty:
        st.sidebar.subheader("📈 פוזיציות (Live)")
        for _, row in open_trades_display.iterrows():
            p_color = "#00c853" if row['PnL_Net'] >= 0 else "#ff4b4b"
            st.sidebar.write(f"**{row['Ticker']}:** ${row['Market_Value']:,.2f}")
            st.sidebar.markdown(f"<p style='color:{p_color}; margin-top:-15px; text-align:right;'>{'+' if row['PnL_Net'] >= 0 else ''}{row['PnL_Net']:,.2f}$ ({row['PnL_Pct']:.2f}%)</p>", unsafe_allow_html=True)

    st.title("📊 יומן המסחר של אבי")
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades_display.empty:
            df_disp = open_trades_display[['Ticker', 'Entry_Date', 'Qty', 'Market_Value', 'PnL_Net', 'PnL_Pct', 'סיבת כניסה']].copy()
            df_disp['PnL_Pct'] = df_disp['PnL_Pct'].map("{:.2f}%".format)
            st.dataframe(df_disp.sort_values('Market_Value', ascending=False), use_container_width=True, hide_index=True)

    with t2:
        if not closed_trades.empty:
            total_realized = closed_trades['PnL'].sum()
            pnl_color = "green" if total_realized >= 0 else "red"
            st.markdown(f"<div style='text-align: right; direction: rtl;'><h3>סך רווח ממומש: <span style='color:{pnl_color}; direction: ltr; unicode-bidi: bidi-override;'>${total_realized:,.2f}</span></h3></div>", unsafe_allow_html=True)
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'Entry_Price', 'Exit_Price', 'PnL', 'סיבת כניסה', 'סיבת יציאה']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
