import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")

# רענון בטוח
st_autorefresh(interval=10000, key="html_table_refresh")

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

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${CASH_NOW:,.2f}")
    total_portfolio = market_val_total + CASH_NOW
    diff = total_portfolio - initial_portfolio_value
    st.sidebar.write(f"### שווי תיק כולל")
    st.sidebar.write(f"## ${total_portfolio:,.2f}")
    diff_color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{diff_color}; font-size: 20px; font-weight: bold; margin-top:-10px;'>{'+' if diff >= 0 else ''}{diff:,.2f}$</p>", unsafe_allow_html=True)
    
    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades.empty:
            st.dataframe(open_trades[['Ticker', 'Entry_Date', 'Qty', 'Entry_Price', 'Market_Value', 'PnL_Net', 'PnL_Pct', 'סיבת כניסה']], use_container_width=True, hide_index=True)
    
    with t2:
        if not closed_trades.empty:
            st.markdown(f"### סך רווח ממומש: :green[${closed_trades['PnL'].sum():,.2f}]")
            st.divider()
            
            # --- פתרון שבירת השורות (HTML Table) ---
            # עיצוב ה-CSS שיכריח את הטקסט להישבר (Wrap)
            html_style = """
            <style>
                .custom-table {
                    width: 100%;
                    border-collapse: collapse;
                    font-family: sans-serif;
                    font-size: 14px;
                }
                .custom-table th {
                    background-color: #f0f2f6;
                    text-align: right;
                    padding: 10px;
                    border: 1px solid #ddd;
                }
                .custom-table td {
                    text-align: right;
                    padding: 10px;
                    border: 1px solid #ddd;
                    white-space: normal; /* כאן קורה הקסם - שבירת שורה */
                    word-wrap: break-word;
                    max-width: 300px;
                }
                .pnl-pos { color: #00c853; font-weight: bold; }
                .pnl-neg { color: #ff4b4b; font-weight: bold; }
            </style>
            """
            
            # בניית הטבלה כשורה של פקודות HTML
            table_header = """
            <table class='custom-table'>
                <thead>
                    <tr>
                        <th>טיקר</th><th>כניסה</th><th>יציאה</th><th>כמות</th><th>רווח/הפסד</th><th>סיבת כניסה</th><th>סיבת יציאה</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            rows = ""
            for _, row in closed_trades.iterrows():
                pnl_class = 'pnl-pos' if row['PnL'] >= 0 else 'pnl-neg'
                rows += f"""
                <tr>
                    <td><b>{row['Ticker']}</b></td>
                    <td>{row['Entry_Date']}</td>
                    <td>{row['Exit_Date']}</td>
                    <td>{row['Qty']}</td>
                    <td class='{pnl_class}'>${row['PnL']:.2f}</td>
                    <td>{row['סיבת כניסה']}</td>
                    <td>{row['סיבת יציאה']}</td>
                </tr>
                """
            
            full_html = html_style + table_header + rows + "</tbody></table>"
            st.markdown(full_html, unsafe_allow_html=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
