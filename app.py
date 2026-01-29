import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")

# רענון בטוח לענן
st_autorefresh(interval=10000, key="fixed_wrap_refresh")

SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"
CASH_NOW = 4957.18 
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
    
    raw_open = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull())].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()
    
    market_val_total = 0
    open_trades = pd.DataFrame()
    if not raw_open.empty:
        raw_open['temp_fee'] = raw_open['Qty'].apply(calculate_trade_fee)
        open_trades = raw_open.groupby('Ticker').agg({
            'Qty': 'sum', 'עלות כניסה': 'sum', 'temp_fee': 'sum', 'Entry_Date': 'min',
            'סיבת כניסה': lambda x: " | ".join(set(x.dropna().astype(str)))
        }).reset_index()
        open_trades['Entry_Price'] = open_trades['עלות כניסה'] / open_trades['Qty']
        
        tickers = list(open_trades['Ticker'].unique())
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        live_list = []
        for _, row in open_trades.iterrows():
            t = row['Ticker']
            curr = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            val = curr * row['Qty']
            pnl_usd = (val - row['עלות כניסה']) - row['temp_fee']
            pnl_pct = ((curr - row['Entry_Price']) / row['Entry_Price']) * 100
            market_val_total += val
            live_list.append({'Ticker': t, 'Market_Value': val, 'PnL_Net': pnl_usd, 'PnL_Pct': pnl_pct})
        open_trades = open_trades.merge(pd.DataFrame(live_list), on='Ticker')

    fees_closed = (closed_trades['Qty'].apply(calculate_trade_fee).sum() * 2)
    total_fees = (open_trades['temp_fee'].sum() if not open_trades.empty else 0) + fees_closed

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${CASH_NOW:,.2f}")
    total_portfolio = market_val_total + CASH_NOW
    diff = total_portfolio - initial_portfolio_value
    st.sidebar.write(f"### שווי תיק כולל")
    st.sidebar.write(f"## ${total_portfolio:,.2f}")
    diff_color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{diff_color}; font-size: 20px; font-weight: bold; margin-top:-10px;'>{'+' if diff >= 0 else ''}{diff:,.2f}$</p>", unsafe_allow_html=True)
    st.sidebar.write("📉 **עלויות מסחר מצטברות:**")
    st.sidebar.markdown(f"<p style='color:#ff4b4b; font-size: 18px; font-weight: bold; margin-top:-10px;'>-${total_fees:,.2f}</p>", unsafe_allow_html=True)

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    st.link_button("📂 פתח גיליון לעדכון", SHEET_URL, use_container_width=True, type="primary")
    
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades.empty:
            df_disp = open_trades[['Ticker', 'Entry_Date', 'Qty', 'Entry_Price', 'Market_Value', 'PnL_Net', 'PnL_Pct', 'סיבת כניסה']].copy()
            df_disp['PnL_Pct'] = df_disp['PnL_Pct'].map("{:.2f}%".format)
            st.dataframe(df_disp.sort_values('Market_Value', ascending=False), use_container_width=True, hide_index=True)
            st.divider()
            chart_data = pd.concat([open_trades[['Ticker', 'Market_Value']], pd.DataFrame([{'Ticker': 'CASH', 'Market_Value': CASH_NOW}])], ignore_index=True)
            fig = px.pie(chart_data, values='Market_Value', names='Ticker', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig, use_container_width=True)
    
    with t2:
        if not closed_trades.empty:
            total_realized = closed_trades['PnL'].sum()
            # תיקון תצוגת רווח ממומש למניעת היפוך סימנים (LTR)
            pnl_color = "green" if total_realized >= 0 else "red"
            st.markdown(f"### סך רווח ממומש: <span style='color:{pnl_color}; direction: ltr; unicode-bidi: bidi-override;'>${total_realized:,.2f}</span>", unsafe_allow_html=True)
            st.divider()
            
            # הצגת הטבלה המקורית עם שבירת שורות מובנית
            st.dataframe(
                closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'Entry_Price', 'Exit_Price', 'PnL', 'סיבת כניסה', 'סיבת יציאה']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "סיבת כניסה": st.column_config.TextColumn("סיבת כניסה", width="large", required=True),
                    "סיבת יציאה": st.column_config.TextColumn("סיבת יציאה", width="large", required=True)
                }
            )

except Exception as e:
    st.error(f"שגיאה: {e}")
