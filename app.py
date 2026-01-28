import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
import plotly.express as px

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק - תצוגה מאוחדת וניתוח ויזואלי")

SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

# --- נתוני אמת ---
CASH_NOW = 4957.18 
initial_portfolio_value = 44302.55

conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()

    # פונקציית עמלה (3.5$ + 0.0078$ למניה)
    def calculate_trade_fee(qty):
        return 3.50 + (qty * 0.0078) if qty > 0 else 0

    # המרת עמודות למספרים
    numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'עלות יציאה', 'PnL']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # הפרדה
    raw_open = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # --- איחוד פוזיציות גלובלי ---
    if not raw_open.empty:
        raw_open['temp_fee'] = raw_open['Qty'].apply(calculate_trade_fee)
        
        # איחוד כולל עמודת "סיבת כניסה" - אנחנו מאחדים את הטקסט אם יש כמה כניסות
        open_trades = raw_open.groupby('Ticker').agg({
            'Qty': 'sum',
            'עלות כניסה': 'sum',
            'temp_fee': 'sum',
            'Entry_Date': 'min',
            'סיבת כניסה': lambda x: " | ".join(set(x.dropna().astype(str))) # איחוד סיבות ייחודיות
        }).reset_index()
        
        open_trades['Entry_Price'] = open_trades['עלות כניסה'] / open_trades['Qty']
    else:
        open_trades = pd.DataFrame()

    # --- משיכת נתוני שוק לייב ---
    market_val_total = 0
    total_unrealized_pnl = 0
    
    if not open_trades.empty:
        tickers = open_trades['Ticker'].unique()
        data = yf.download(list(tickers), period="1d", progress=False)['Close']
        
        live_data = []
        for _, row in open_trades.iterrows():
            t = row['Ticker']
            curr = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            val = curr * row['Qty']
            pnl = (val - row['עלות כניסה']) - row['temp_fee']
            
            market_val_total += val
            total_unrealized_pnl += pnl
            live_data.append({'Ticker': t, 'Market_Value': val, 'PnL_Net': pnl})
        
        live_stats = pd.DataFrame(live_data)
        open_trades = open_trades.merge(live_stats, on='Ticker')

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ נתוני חשבון")
    st.sidebar.metric("מזומן פנוי", f"${CASH_NOW:,.2f}")
    
    total_portfolio = market_val_total + CASH_NOW
    st.sidebar.divider()
    st.sidebar.metric("שווי תיק כולל", f"${total_portfolio:,.2f}", 
                      delta=f"${total_unrealized_pnl:,.2f} (נטו)")

    # --- מסך ראשי: גרף התפלגות ---
    if not open_trades.empty:
        st.subheader("🍕 התפלגות תיק המניות (לפי שווי שוק)")
        chart_data = open_trades[['Ticker', 'Market_Value']].copy()
        cash_row = pd.DataFrame([{'Ticker': 'CASH', 'Market_Value': CASH_NOW}])
        chart_data = pd.concat([chart_data, cash_row], ignore_index=True)
        
        fig = px.pie(chart_data, values='Market_Value', names='Ticker', 
                     hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig.update_traces(textinfo='percent+label', pull=[0.05]*len(chart_data))
        st.plotly_chart(fig, use_container_width=True)

    # --- טאבים לטבלאות ---
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות (מאוחד)", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades.empty:
            # הסתרת ה-Index באמצעות hide_index=True
            display_cols_open = ['Ticker', 'Entry_Date', 'Qty', 'Entry_Price', 'Market_Value', 'PnL_Net', 'סיבת כניסה']
            st.dataframe(
                open_trades[display_cols_open].sort_values('Market_Value', ascending=False), 
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.info("אין פוזיציות פתוחות.")

    with t2:
        if not closed_trades.empty:
            # הסתרת ה-Index והוספת סיבות כניסה ויציאה
            display_cols_closed = [
                'Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'Entry_Price', 'Exit_Price', 
                'PnL', 'סיבת כניסה', 'סיבת יציאה'
            ]
            st.dataframe(
                closed_trades[display_cols_closed].sort_values('Exit_Date', ascending=False), 
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.info("אין היסטוריית טריידים.")

except Exception as e:
    st.error(f"שגיאה: {e}")
