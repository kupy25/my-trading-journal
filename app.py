import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
import plotly.express as px

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")

SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"
CASH_NOW = 4957.18 
initial_portfolio_value = 44302.55

def calculate_trade_fee(qty):
    return 3.50 + (qty * (0.0048 + 0.003)) if qty > 0 else 0

conn = st.connection("gsheets", type=GSheetsConnection)

# --- פונקציית ליבה לשליפת נתונים ---
def fetch_processed_data():
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    for col in ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    raw_open = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull())].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()
    
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
            live_list.append({'Ticker': t, 'Market_Value': val, 'PnL_Net': pnl_usd, 'PnL_Pct': pnl_pct})
        
        return open_trades.merge(pd.DataFrame(live_list), on='Ticker'), closed_trades
    return pd.DataFrame(), closed_trades

# --- רכיבי SIDEBAR (חלק סטטי) ---
st.sidebar.header("⚙️ ניהול חשבון")
st.sidebar.metric("מזומן פנוי", f"${CASH_NOW:,.2f}")

# --- רענון שקט לנתוני התיק ב-SIDEBAR ---
with st.sidebar:
    @st.fragment(run_every=10)
    def sidebar_live_metrics():
        open_trades, closed_trades = fetch_processed_data()
        
        mkt_total = open_trades['Market_Value'].sum() if not open_trades.empty else 0
        total_portfolio = mkt_total + CASH_NOW
        diff = total_portfolio - initial_portfolio_value
        fees_closed = (closed_trades['Qty'].apply(calculate_trade_fee).sum() * 2)
        total_fees = (open_trades['temp_fee'].sum() if not open_trades.empty else 0) + fees_closed
        
        st.write(f"### שווי תיק כולל")
        st.write(f"## ${total_portfolio:,.2f}")
        diff_color = "#00c853" if diff >= 0 else "#ff4b4b"
        st.markdown(f"<p style='color:{diff_color}; font-size: 20px; font-weight: bold; margin-top:-10px;'>{'+' if diff >= 0 else ''}{diff:,.2f}$</p>", unsafe_allow_html=True)
        
        st.write("📉 **עלויות מסחר מצטברות:**")
        st.markdown(f"<p style='color:#ff4b4b; font-size: 18px; font-weight: bold; margin-top:-10px;'>-${total_fees:,.2f}</p>", unsafe_allow_html=True)
        
        st.divider()
        if not open_trades.empty:
            st.subheader("📈 פוזיציות (Live)")
            for _, row in open_trades.iterrows():
                p_color = "#00c853" if row['PnL_Net'] >= 0 else "#ff4b4b"
                st.write(f"**{row['Ticker']}:** ${row['Market_Value']:,.2f}")
                st.markdown(f"<p style='color:{p_color}; margin-top:-15px;'>{'+' if row['PnL_Net'] >= 0 else ''}{row['PnL_Net']:,.2f}$ ({row['PnL_Pct']:.2f}%)</p>", unsafe_allow_html=True)
    
    sidebar_live_metrics()

with st.sidebar.popover("🧮 מחשבון טרייד", use_container_width=True):
    st.subheader("מחשבון גודל פוזיציה")
    c_ticker = st.text_input("טיקר", key="calc_t")
    c_entry = st.number_input("כניסה $", value=0.0, key="calc_e")
    c_stop = st.number_input("סטופ $", value=0.0, key="calc_s")
    if c_ticker and c_entry > c_stop:
        q = min(int((initial_portfolio_value * 0.01) / (c_entry - c_stop)), int(CASH_NOW / c_entry))
        st.success(f"כמות: {q} | עלות: ${q*c_entry:,.2f}")

# --- רענון שקט למסך הראשי ---
@st.fragment(run_every=10)
def main_content_update():
    open_trades, closed_trades = fetch_processed_data()
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
        else: st.info("אין פוזיציות פתוחות")
    
    with t2:
        if not closed_trades.empty:
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'Entry_Price', 'Exit_Price', 'PnL', 'סיבת כניסה', 'סיבת יציאה']], use_container_width=True, hide_index=True)
            total_realized = closed_trades['PnL'].sum()
            st.markdown(f"### סך רווח ממומש: :{'green' if total_realized >= 0 else 'red'}[${total_realized:,.2f}]")

main_content_update()
