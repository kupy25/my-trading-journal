import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")

# רענון אוטומטי - 10 שניות (Verified)
st_autorefresh(interval=10000, key="fixed_verified_refresh")

# עיצוב כותרות בלבד לימין (בלי לשבור את המספרים)
st.markdown("""
    <style>
    h1, h2, h3 { text-align: right; direction: rtl; }
    .stTabs { direction: rtl; }
    </style>
    """, unsafe_allow_html=True)

SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

# נקודת הייחוס למזומן (לפני הקניות שתועדו ביומן)
CASH_REFERENCE = 4957.18  
INITIAL_TOTAL_VALUE = 44302.55

def calculate_trade_fee(qty):
    return 3.50 + (qty * (0.0048 + 0.003)) if qty > 0 else 0

conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # קריאת הנתונים
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    
    for col in ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # הפרדה לפתוחות וסגורות
    open_mask = (df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")
    raw_open = df[open_mask].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # חישוב עמלות דינמי
    fees_on_open = raw_open['Qty'].apply(calculate_trade_fee).sum()
    fees_on_closed = (closed_trades['Qty'].apply(calculate_trade_fee).sum() * 2)
    total_fees_display = fees_on_open + fees_on_closed

    # חישוב מזומן פנוי דינמי (נקודת ייחוס פחות עלות קניות פתוחות ועמלותיהן)
    invested_in_open = raw_open['עלות כניסה'].sum()
    current_cash = CASH_REFERENCE - invested_in_open - fees_on_open

    # עיבוד נתוני לייב
    market_val_total = 0
    open_trades_display = pd.DataFrame()
    
    if not raw_open.empty:
        open_trades_summary = raw_open.groupby('Ticker').agg({
            'Qty': 'sum', 'עלות כניסה': 'sum', 'Entry_Date': 'min',
            'סיבת כניסה': lambda x: " | ".join(set(x.dropna().astype(str)))
        }).reset_index()
        
        tickers = list(open_trades_summary['Ticker'].unique())
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        live_list = []
        for _, row in open_trades_summary.iterrows():
            t = row['Ticker']
            curr_price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            val = curr_price * row['Qty']
            market_val_total += val
            
            entry_avg = row['עלות כניסה'] / row['Qty']
            pnl_val = (val - row['עלות כניסה']) - calculate_trade_fee(row['Qty'])
            pnl_pct = ((curr_price - entry_avg) / entry_avg) * 100
            live_list.append({'Ticker': t, 'Market_Value': val, 'PnL_Net': pnl_val, 'PnL_Pct': pnl_pct})
        
        open_trades_display = open_trades_summary.merge(pd.DataFrame(live_list), on='Ticker')

    # --- SIDEBAR (מסודר ותקין) ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${current_cash:,.2f}")
    
    total_portfolio = market_val_total + current_cash
    total_diff = total_portfolio - INITIAL_TOTAL_VALUE
    
    st.sidebar.write("### שווי תיק כולל")
    st.sidebar.write(f"## ${total_portfolio:,.2f}")
    
    diff_color = "#00c853" if total_diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{diff_color}; font-size: 20px; font-weight: bold; margin-top:-10px;'>{'+' if total_diff >= 0 else ''}{total_diff:,.2f}$</p>", unsafe_allow_html=True)
    
    st.sidebar.write("📉 **עלויות מסחר מצטברות:**")
    st.sidebar.markdown(f"<p style='color:#ff4b4b; font-size: 18px; font-weight: bold; margin-top:-10px;'>-${total_fees_display:,.2f}</p>", unsafe_allow_html=True)

    if not open_trades_display.empty:
        st.sidebar.divider()
        st.sidebar.subheader("📈 פוזיציות (Live)")
        for _, row in open_trades_display.iterrows():
            p_color = "#00c853" if row['PnL_Net'] >= 0 else "#ff4b4b"
            st.sidebar.write(f"**{row['Ticker']}:** ${row['Market_Value']:,.2f}")
            st.sidebar.markdown(f"<p style='color:{p_color}; margin-top:-15px;'>{'+' if row['PnL_Net'] >= 0 else ''}{row['PnL_Net']:,.2f}$ ({row['PnL_Pct']:.2f}%)</p>", unsafe_allow_html=True)

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades_display.empty:
            df_view = open_trades_display[['Ticker', 'Entry_Date', 'Qty', 'Market_Value', 'PnL_Net', 'PnL_Pct', 'סיבת כניסה']].copy()
            df_view['PnL_Pct'] = df_view['PnL_Pct'].map("{:.2f}%".format)
            st.dataframe(df_view.sort_values('Market_Value', ascending=False), use_container_width=True, hide_index=True)
    
    with t2:
        if not closed_trades.empty:
            realized = closed_trades['PnL'].sum()
            st.write(f"### סך רווח ממומש: ${realized:,.2f}")
            st.dataframe(
                closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'Entry_Price', 'Exit_Price', 'PnL', 'סיבת כניסה', 'סיבת יציאה']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "סיבת כניסה": st.column_config.TextColumn("סיבת כניסה", width="large"),
                    "סיבת יציאה": st.column_config.TextColumn("סיבת יציאה", width="large")
                }
            )

except Exception as e:
    st.error(f"שגיאה בטעינה: {e}")
