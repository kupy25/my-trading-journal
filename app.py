import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key="verified_static_cash")

# 2. נתוני בסיס
PORTFOLIO_START_VAL = 44302.55 #

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

def color_pnl(val):
    try:
        color = 'red' if val < 0 else 'green'
        return f'color: {color}; font-weight: bold;'
    except: return ''

# 3. חיבור לגיליון
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    
    # משיכת מזומן סטטי מעמודה N שורה 2 (מזומן_עדכני)
    # אנו לוקחים את הערך הראשון שנמצא בעמודה הזו
    if 'מזומן_עדכני' in df.columns:
        dynamic_cash = pd.to_numeric(df['מזומן_עדכני'], errors='coerce').iloc[0]
    else:
        dynamic_cash = 0.0
        st.sidebar.warning("עמודה 'מזומן_עדכני' לא נמצאה בגיליון")

    # המרת שאר העמודות
    for col in ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # הפרדה
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # חישוב עמלות מצטברות לצורך תצוגה בלבד
    total_fees = (df['Qty'].apply(get_fee).sum()) + (closed_trades['Qty'].apply(get_fee).sum())

    # נתוני לייב
    market_val_total = 0
    live_list = []
    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum', 'סיבת כניסה': 'first'}).reset_index()
        tickers = [t for t in summary['Ticker'].unique() if t]
        if tickers:
            data = yf.download(tickers, period="1d", progress=False)['Close']
            for _, row in summary.iterrows():
                t = row['Ticker']
                price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
                val = price * row['Qty']
                market_val_total += val
                avg_cost = row['עלות כניסה'] / row['Qty']
                pnl_usd = (val - row['עלות כניסה']) - get_fee(row['Qty'])
                pnl_pct = ((price - avg_cost) / avg_cost) * 100
                live_list.append({'Ticker': t, 'כמות': row['Qty'], 'שווי': val, 'רווח_דולרי': pnl_usd, 'רווח_אחוז': pnl_pct, 'סיבת כניסה': row['סיבת כניסה']})
        live_df = pd.DataFrame(live_list)

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${dynamic_cash:,.2f}")
    
    total_portfolio_now = market_val_total + dynamic_cash
    diff_ytd = total_portfolio_now - PORTFOLIO_START_VAL
    
    st.sidebar.write("### שווי תיק כולל")
    st.sidebar.write(f"## ${total_portfolio_now:,.2f}")
    
    # תיקון תצוגת רווח/הפסד (ירוק/אדום)
    c_ytd = "#00c853" if diff_ytd >= 0 else "#ff4b4b"
    icon = "▲" if diff_ytd >= 0 else "▼"
    st.sidebar.markdown(f"<h3 style='color:{c_ytd}; margin:0;'>{icon} ${abs(diff_ytd):,.2f}</h3>", unsafe_allow_html=True)
    
    st.sidebar.write("📉 **עמלות מצטברות:**")
    st.sidebar.markdown(f"<p style='color:#ff4b4b; font-size: 18px; font-weight: bold;'>-${total_fees:,.2f}</p>", unsafe_allow_html=True)

    # מחשבון בתוך פופ-אובר לחיסכון במקום
    st.sidebar.divider()
    with st.sidebar.expander("🧮 מחשבון טרייד חדש"):
        c_entry = st.number_input("כניסה $", value=0.0)
        c_stop = st.number_input("סטופ $", value=0.0)
        if c_entry > c_stop:
            risk = PORTFOLIO_START_VAL * 0.01
            qty = int(risk / (c_entry - c_stop))
            st.success(f"כמות: {qty} | עלות: ${qty*c_entry:,.2f}")

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    st.link_button("📂 פתח גוגל שיט", "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit")

    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    with t1:
        if not live_list == []:
            st.dataframe(live_df.style.map(color_pnl, subset=['רווח_דולרי', 'רווח_אחוז']), use_container_width=True, hide_index=True)
            st.divider()
            st.subheader("🥧 התפלגות תיק")
            pie_data = pd.concat([live_df[['Ticker', 'שווי']].rename(columns={'שווי': 'Value'}), pd.DataFrame([{'Ticker': 'מזומן', 'Value': dynamic_cash}])])
            fig = px.pie(pie_data, values='Value', names='Ticker', hole=0.4)
            fig.update_traces(textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)

    with t2:
        if not closed_trades.empty:
            realized_sum = closed_trades['PnL'].sum()
            st.markdown(f"### סך רווח ממומש: <span style='color:{'green' if realized_sum >=0 else 'red'};'>${realized_sum:,.2f}</span>", unsafe_allow_html=True)
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL', 'סיבת כניסה', 'סיבת יציאה']].sort_values('Exit_Date', ascending=False), use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
