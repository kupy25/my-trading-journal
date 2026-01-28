import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
import time

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")

# --- נתוני אמת קבועים ---
CASH_NOW = 4957.18 
initial_portfolio_value = 44302.55

# פונקציית העמלות שלך
def calculate_trade_fee(qty):
    return 3.50 + (qty * (0.0048 + 0.003)) if qty > 0 else 0

conn = st.connection("gsheets", type=GSheetsConnection)

# שימוש ב-placeholder כדי לרענן רק את התוכן
placeholder = st.empty()

# לולאת רענון אינסופית (כל 10 שניות)
while True:
    with placeholder.container():
        try:
            df = conn.read(ttl="0")
            df.columns = df.columns.str.strip()

            # המרת נתונים
            numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'עלות יציאה', 'PnL']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            raw_open = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
            closed_trades = df[df['Exit_Price'] > 0].copy()

            # חישוב עמלות
            fees_on_open = raw_open['Qty'].apply(calculate_trade_fee).sum()
            fees_on_closed = (closed_trades['Qty'].apply(calculate_trade_fee).sum() * 2) 
            total_annual_fees = fees_on_open + fees_on_closed

            # איחוד פוזיציות
            if not raw_open.empty:
                raw_open['temp_fee'] = raw_open['Qty'].apply(calculate_trade_fee)
                open_trades = raw_open.groupby('Ticker').agg({
                    'Qty': 'sum', 'עלות כניסה': 'sum', 'temp_fee': 'sum', 'Entry_Date': 'min',
                    'סיבת כניסה': lambda x: " | ".join(set(x.dropna().astype(str)))
                }).reset_index()
                open_trades['Entry_Price'] = open_trades['עלות כניסה'] / open_trades['Qty']
            else:
                open_trades = pd.DataFrame()

            # נתוני שוק
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
                    pnl_usd = (val - row['עלות כניסה']) - row['temp_fee']
                    pnl_pct = ((curr - row['Entry_Price']) / row['Entry_Price']) * 100
                    market_val_total += val
                    total_unrealized_pnl += pnl_usd
                    live_data.append({'Ticker': t, 'Market_Value': val, 'PnL_Net': pnl_usd, 'PnL_Pct': pnl_pct})
                open_trades = open_trades.merge(pd.DataFrame(live_data), on='Ticker')

            # --- תצוגת SIDEBAR ---
            total_portfolio = market_val_total + CASH_NOW
            portfolio_diff = total_portfolio - initial_portfolio_value
            diff_color = "#00c853" if portfolio_diff >= 0 else "#ff4b4b"
            
            st.sidebar.header("⚙️ נתוני חשבון")
            st.sidebar.metric("מזומן פנוי", f"${CASH_NOW:,.2f}")
            st.sidebar.write(f"### שווי תיק כולל")
            st.sidebar.write(f"## ${total_portfolio:,.2f}")
            st.sidebar.markdown(f"<p style='color:{diff_color}; font-size: 20px; font-weight: bold; margin-top:-10px;'>{'+' if portfolio_diff >= 0 else ''}{portfolio_diff:,.2f}$</p>", unsafe_allow_html=True)
            st.sidebar.write("📉 **עלויות מסחר מצטברות:**")
            st.sidebar.markdown(f"<p style='color:#ff4b4b; font-size: 18px; font-weight: bold; margin-top:-10px;'>-${total_annual_fees:,.2f}</p>", unsafe_allow_html=True)

            st.sidebar.divider()
            with st.sidebar.popover("🧮 מחשבון טרייד חדש", use_container_width=True):
                st.subheader("מחשבון גודל פוזיציה")
                calc_t = st.text_input("טיקר", "").upper()
                e_p = st.number_input("מחיר כניסה $", value=0.0, step=0.01)
                s_p = st.number_input("סטופ לוס $", value=0.0, step=0.01)
                if calc_t and e_p > s_p:
                    risk_amt = initial_portfolio_value * 0.01
                    qty = min(int(risk_amt / (e_p - s_p)), int(CASH_NOW / e_p))
                    st.success(f"כמות: {qty} | עלות: ${qty*e_p:,.2f}")

            st.sidebar.subheader("📈 פוזיציות (Live)")
            if not open_trades.empty:
                for _, row in open_trades.iterrows():
                    p_color = "#00c853" if row['PnL_Net'] >= 0 else "#ff4b4b"
                    st.sidebar.write(f"**{row['Ticker']}:** ${row['Market_Value']:,.2f}")
                    st.sidebar.markdown(f"<p style='color:{p_color}; margin-top:-15px;'>{'+' if row['PnL_Net'] >= 0 else ''}{row['PnL_Net']:,.2f}$ ({row['PnL_Pct']:.2f}%)</p>", unsafe_allow_html=True)

            # --- מסך ראשי ---
            st.title("📊 יומן מסחר - רענון אוטומטי (10 ש')")
            t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
            with t1:
                if not open_trades.empty:
                    st.dataframe(open_trades[['Ticker', 'Entry_Date', 'Qty', 'Entry_Price', 'Market_Value', 'PnL_Net', 'PnL_Pct', 'סיבת כניסה']].sort_values('Market_Value', ascending=False), use_container_width=True, hide_index=True)
                    st.divider()
                    chart_data = open_trades[['Ticker', 'Market_Value']].copy()
                    chart_data = pd.concat([chart_data, pd.DataFrame([{'Ticker': 'CASH', 'Market_Value': CASH_NOW}])], ignore_index=True)
                    fig = px.pie(chart_data, values='Market_Value', names='Ticker', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                    st.plotly_chart(fig, use_container_width=True)
            with t2:
                if not closed_trades.empty:
                    st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'Entry_Price', 'Exit_Price', 'PnL', 'סיבת כניסה', 'סיבת יציאה']].sort_values('Exit_Date', ascending=False), use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"שגיאה: {e}")

    # המתנה של 10 שניות לפני הריצה הבאה
    time.sleep(10)
