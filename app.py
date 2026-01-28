import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
import plotly.express as px

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק - תצוגה מאוחדת")

SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

# --- נתוני אמת קבועים ---
CASH_NOW = 4957.18 
initial_portfolio_value = 44302.55

conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()

    # פונקציית עמלה לפי טבלת הברוקר
    def calculate_trade_fee(qty):
        return 3.50 + (qty * (0.0048 + 0.003)) if qty > 0 else 0

    # המרת עמודות למספרים
    numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'עלות יציאה', 'PnL']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # הפרדה לפתוחים וסגורים
    raw_open = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # --- איחוד פוזיציות גלובלי ---
    if not raw_open.empty:
        raw_open['temp_fee'] = raw_open['Qty'].apply(calculate_trade_fee)
        open_trades = raw_open.groupby('Ticker').agg({
            'Qty': 'sum',
            'עלות כניסה': 'sum',
            'temp_fee': 'sum',
            'Entry_Date': 'min',
            'סיבת כניסה': lambda x: " | ".join(set(x.dropna().astype(str)))
        }).reset_index()
        open_trades['Entry_Price'] = open_trades['עלות כניסה'] / open_trades['Qty']
    else:
        open_trades = pd.DataFrame()

    # --- משיכת נתוני שוק לייב ---
    market_val_total = 0
    total_unrealized_pnl = 0
    live_data_list = []
    
    if not open_trades.empty:
        tickers = open_trades['Ticker'].unique()
        data = yf.download(list(tickers), period="1d", progress=False)['Close']
        
        for _, row in open_trades.iterrows():
            t = row['Ticker']
            curr = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            val = curr * row['Qty']
            pnl = (val - row['עלות כניסה']) - row['temp_fee']
            
            market_val_total += val
            total_unrealized_pnl += pnl
            live_data_list.append({'Ticker': t, 'Market_Value': val, 'PnL_Net': pnl})
        
        open_trades = open_trades.merge(pd.DataFrame(live_data_list), on='Ticker')

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ נתוני חשבון")
    st.sidebar.metric("מזומן פנוי", f"${CASH_NOW:,.2f}")
    
    # מחשבון
    st.sidebar.divider()
    st.sidebar.subheader("🧮 מחשבון טרייד")
    calc_t = st.sidebar.text_input("טיקר לבדיקה", "").upper()
    e_p = st.sidebar.number_input("מחיר כניסה $", value=0.0)
    s_p = st.sidebar.number_input("סטופ לוס $", value=0.0)
    if calc_t and e_p > s_p:
        qty = min(int((initial_portfolio_value * 0.01) / (e_p - s_p)), int(CASH_NOW / e_p))
        st.sidebar.success(f"כמות: {qty} | עלות: ${qty*e_p:,.2f}")

    # פוזיציות לייב בסידבר
    st.sidebar.divider()
    st.sidebar.subheader("📈 פוזיציות (Live)")
    if not open_trades.empty:
        for _, row in open_trades.iterrows():
            st.sidebar.write(f"**{row['Ticker']}:** ${row['Market_Value']:,.2f}")
            color = "#00c853" if row['PnL_Net'] >= 0 else "#ff4b4b"
            st.sidebar.markdown(f"<p style='color:{color}; margin-top:-15px;'>{'+' if row['PnL_Net'] >= 0 else ''}{row['PnL_Net']:,.2f}$</p>", unsafe_allow_html=True)

    # סיכום תיק - תיקון הצבע והחץ
    total_portfolio = market_val_total + CASH_NOW
    portfolio_diff = total_portfolio - initial_portfolio_value
    
    st.sidebar.divider()
    # שימוש ב-delta_color="normal" מבטיח שאדום יהיה לירידה וירוק לעלייה
    st.sidebar.metric(
        label="שווי תיק כולל", 
        value=f"${total_portfolio:,.2f}", 
        delta=f"${portfolio_diff:,.2f}",
        delta_color="normal" 
    )

    # --- מסך ראשי ---
    st.link_button("📂 פתח גיליון לעדכון", SHEET_URL, use_container_width=True, type="primary")
    
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות (מאוחד)", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades.empty:
            # hide_index=True מעלים את העמודה השמאלית המיותרת
            display_cols_open = ['Ticker', 'Entry_Date', 'Qty', 'Entry_Price', 'Market_Value', 'PnL_Net', 'סיבת כניסה']
            st.dataframe(
                open_trades[display_cols_open].sort_values('Market_Value', ascending=False), 
                use_container_width=True, 
                hide_index=True
            )
        else: st.info("אין פוזיציות פתוחות.")

    with t2:
        if not closed_trades.empty:
            # הצגת סיבות כניסה ויציאה בטריידים סגורים
            display_cols_closed = [
                'Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'Entry_Price', 'Exit_Price', 
                'PnL', 'סיבת כניסה', 'סיבת יציאה'
            ]
            st.dataframe(
                closed_trades[display_cols_closed].sort_values('Exit_Date', ascending=False), 
                use_container_width=True, 
                hide_index=True
            )

    # --- גרף פאי בתחתית ---
    if not open_trades.empty:
        st.divider()
        st.subheader("🍕 התפלגות הון מושקע")
        chart_data = open_trades[['Ticker', 'Market_Value']].copy()
        chart_data = pd.concat([chart_data, pd.DataFrame([{'Ticker': 'CASH', 'Market_Value': CASH_NOW}])], ignore_index=True)
        fig = px.pie(chart_data, values='Market_Value', names='Ticker', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
