import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון אוטומטי
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=15000, key="datarefresh")

# הגדרת שווי התחלה לחישוב תשואה כללית
PORTFOLIO_START_VAL = 44302.55 

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

# 2. חיבור וקריאת נתונים
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    
    # ניקוי נתונים נומריים
    numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL', 'מזומן_עדכני']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # שליפת המזומן העדכני מהגיליון (לוקח את הערך הלא-אפס האחרון)
    cash_series = df['מזומן_עדכני'].replace(0, pd.NA).ffill()
    current_cash = cash_series.iloc[-1] if not cash_series.empty else 0.0

    # מיון פוזיציות
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # חישוב עמלות
    fees_open = open_trades['Qty'].apply(get_fee).sum()
    fees_closed = (closed_trades['Qty'].apply(get_fee).sum() * 2)
    total_fees = fees_open + fees_closed

    # נתוני לייב
    market_val_total = 0
    live_list = []

    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({
            'Qty': 'sum', 
            'עלות כניסה': 'sum',
            'סיבת כניסה': 'first'
        }).reset_index()
        
        tickers = list(summary['Ticker'].unique())
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        for _, row in summary.iterrows():
            t = row['Ticker']
            price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            val = price * row['Qty']
            market_val_total += val
            
            avg_cost = row['עלות כניסה'] / row['Qty']
            pnl_usd = (val - row['עלות כניסה']) - get_fee(row['Qty'])
            pnl_pct = ((price - avg_cost) / avg_cost) * 100
            
            live_list.append({
                'Ticker': t, 
                'כמות': row['Qty'], 
                'שווי': val, 
                'רווח $': pnl_usd, 
                'רווח %': pnl_pct,
                'סיבת כניסה': row['סיבת כניסה']
            })
        
        live_df = pd.DataFrame(live_list)

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי (מהגיליון)", f"${current_cash:,.2f}")
    
    total_portfolio_val = market_val_total + current_cash
    diff = total_portfolio_val - PORTFOLIO_START_VAL
    
    st.sidebar.write("### שווי תיק כולל")
    st.sidebar.write(f"## ${total_portfolio_val:,.2f}")
    
    color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{color}; font-size: 20px; font-weight: bold; margin-top:-10px;'>{'+' if diff >= 0 else ''}{diff:,.2f}$</p>", unsafe_allow_html=True)
    
    st.sidebar.write("📉 **עמלות מצטברות:**")
    st.sidebar.markdown(f"<p style='color:#ff4b4b; font-size: 18px; font-weight: bold; margin-top:-10px;'>-${total_fees:,.2f}</p>", unsafe_allow_html=True)

    # מחשבון טרייד מוטמע מלא
    st.sidebar.divider()
    st.sidebar.subheader("🧮 מחשבון טרייד")
    calc_ticker = st.sidebar.text_input("סימול מניה", value="AAPL")
    c_entry = st.sidebar.number_input("מחיר כניסה $", value=0.0)
    c_stop = st.sidebar.number_input("מחיר סטופ $", value=0.0)
    
    if c_entry > c_stop and c_stop > 0:
        # סיכון של 1% מהתיק
        risk_amount = PORTFOLIO_START_VAL * 0.01
        q = int(risk_amount / (c_entry - c_stop))
        st.sidebar.success(f"מניה: {calc_ticker}\n\nכמות: {q} יח'\n\nעלות: ${q*c_entry:,.2f}")

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    
    # כפתור רענון/מעבר לגיליון
    st.link_button("🔗 מעבר לגיליון גוגל שיטס", "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID")

    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades.empty:
            # עיצוב מותנה לטבלה
            def color_pnl(val):
                if isinstance(val, str): return ''
                color = 'green' if val > 0 else 'red'
                return f'color: {color}'

            styled_df = live_df.style.applymap(color_pnl, subset=['רווח $', 'רווח %'])\
                                     .format({'שווי': "{:,.2f}$", 'רווח $': "{:,.2f}$", 'רווח %': "{:.2f}%"})
            
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            st.divider()
            # גרף פאי
            pie_data = pd.concat([
                live_df[['Ticker', 'שווי']].rename(columns={'שווי': 'Value'}), 
                pd.DataFrame([{'Ticker': 'מזומן', 'Value': current_cash}])
            ])
            fig = px.pie(pie_data, values='Value', names='Ticker', hole=0.4, title="חלוקת נכסים")
            st.plotly_chart(fig, use_container_width=True)

    with t2:
        if not closed_trades.empty:
            realized = closed_trades['PnL'].sum()
            st.markdown(f"### סך רווח ממומש (P&L): <span style='color:{'#00c853' if realized >=0 else '#ff4b4b'};'>${realized:,.2f}</span>", unsafe_allow_html=True)
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL', 'סיבת כניסה', 'סיבת יציאה']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה בעיבוד הנתונים: {e}")
    st.info("וודא ששמות העמודות בגיליון תואמים בדיוק לקוד.")
