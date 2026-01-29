import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px  # הוספתי את השורה החסרה שגרמה לשגיאה
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון (10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key="verified_stable_refresh_v2")

# 2. נקודות ייחוס קבועות
CASH_START = 4957.18  # המזומן ההתחלתי
PORTFOLIO_START_VAL = 44302.55 # שווי התיק ביום פתיחת היומן

# פונקציית עמלות
def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

# 3. חיבור וטעינת נתונים
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    
    for col in ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # הפרדה לפתוחות וסגורות
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # --- חישובי Sidebar דינמיים ---
    invested_in_open = open_trades['עלות כניסה'].sum()
    fees_open = open_trades['Qty'].apply(get_fee).sum()
    
    # חישוב המזומן: התחלה פחות מה שהושקע בפוזיציות פתוחות
    current_cash = CASH_START - invested_in_open - fees_open

    # עמלות מצטברות
    fees_closed = (closed_trades['Qty'].apply(get_fee).sum() * 2)
    total_fees_display = fees_open + fees_closed

    # --- עיבוד נתוני לייב ---
    market_val_total = 0
    live_df = pd.DataFrame()

    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum', 'Entry_Date': 'min'}).reset_index()
        tickers = list(summary['Ticker'].unique())
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        results = []
        for _, row in summary.iterrows():
            t = row['Ticker']
            # בדיקה אם יש יותר מטיקר אחד כדי למשוך את המחיר נכון
            if len(tickers) > 1:
                price = data[t].iloc[-1]
            else:
                price = data.iloc[-1]
                
            val = price * row['Qty']
            market_val_total += val
            
            avg_cost = row['עלות כניסה'] / row['Qty']
            pnl_usd = (val - row['עלות כניסה']) - get_fee(row['Qty'])
            pnl_pct = ((price - avg_cost) / avg_cost) * 100
            results.append({'Ticker': t, 'Market_Value': val, 'PnL_Net': pnl_usd, 'PnL_Pct': pnl_pct})
        live_df = summary.merge(pd.DataFrame(results), on='Ticker')

    # --- SIDEBAR (תצוגה ללא RTL ששובר מספרים) ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${current_cash:,.2f}")
    
    total_val = market_val_total + current_cash
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.subheader("שווי תיק כולל")
    st.sidebar.title(f"${total_val:,.2f}")
    
    color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<h3 style='color:{color}; margin-top:-20px;'>{'+' if diff >= 0 else ''}{diff:,.2f}$</h3>", unsafe_allow_html=True)
    
    st.sidebar.write("📉 **עמלות מצטברות:**")
    st.sidebar.markdown(f"<b style='color:#ff4b4b;'>-${total_fees_display:,.2f}</b>", unsafe_allow_html=True)

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not live_df.empty:
            df_view = live_df[['Ticker', 'Entry_Date', 'Qty', 'Market_Value', 'PnL_Net', 'PnL_Pct']].copy()
            df_view['PnL_Pct'] = df_view['PnL_Pct'].map("{:.2f}%".format)
            st.dataframe(df_view.sort_values('Market_Value', ascending=False), use_container_width=True, hide_index=True)
            st.divider()
            # גרף פיזור
            pie_data = pd.concat([live_df[['Ticker', 'Market_Value']], pd.DataFrame([{'Ticker': 'CASH', 'Market_Value': current_cash}])])
            st.plotly_chart(px.pie(pie_data, values='Market_Value', names='Ticker', hole=0.4, title="פיזור תיק"), use_container_width=True)

    with t2:
        if not closed_trades.empty:
            st.subheader(f"רווח ממומש: ${closed_trades['PnL'].sum():,.2f}")
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL', 'סיבת כניסה', 'סיבת יציאה']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
