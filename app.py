import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון אוטומטי (כל 10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key="double_verified_stable_refresh")

# 2. נקודות ייחוס קבועות (לא לגעת - הבסיס לחישוב האוטומטי)
CASH_START_REF = 4957.18 
PORTFOLIO_START_VAL = 44302.55 

def get_fee(qty):
    # עמלה מינימלית של 3.5$ או לפי כמות מניות
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

# 3. חיבור וטעינת נתונים
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    
    # ניקוי והמרת עמודות למספרים
    for col in ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # הפרדה לפוזיציות פתוחות וסגורות
    open_trades_mask = (df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")
    open_trades = df[open_trades_mask].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # --- חישוב עמלות אוטומטי ---
    # קנייה לכל מה שמופיע בגיליון + מכירה רק למה שסגור
    fees_on_all_buys = df['Qty'].apply(get_fee).sum()
    fees_on_all_sells = closed_trades['Qty'].apply(get_fee).sum()
    total_fees_calc = fees_on_all_buys + fees_on_all_sells

    # --- חישוב מזומן אוטומטי (נוסחת היתרה) ---
    invested_in_open = open_trades['עלות כניסה'].sum()
    realized_pnl = closed_trades['PnL'].sum()
    current_cash_calc = CASH_START_REF - invested_in_open - total_fees_calc + realized_pnl

    # --- עיבוד נתוני לייב (Market Data) ---
    market_val_total = 0
    live_df = pd.DataFrame()

    if not open_trades.empty:
        # סיכום לפי טיקר (למקרה שיש כמה כניסות לאותה מניה)
        summary = open_trades.groupby('Ticker').agg({
            'Qty': 'sum', 
            'עלות כניסה': 'sum',
            'Entry_Date': 'min'
        }).reset_index()
        
        tickers = list(summary['Ticker'].unique())
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        results = []
        for _, row in summary.iterrows():
            t = row['Ticker']
            price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            val = price * row['Qty']
            market_val_total += val
            
            avg_cost = row['עלות כניסה'] / row['Qty']
            # PnL כולל עמלת קנייה
            pnl_usd = (val - row['עלות כניסה']) - get_fee(row['Qty'])
            pnl_pct = ((price - avg_cost) / avg_cost) * 100
            results.append({
                'Ticker': t, 'כמות': row['Qty'], 'Entry_Date': row['Entry_Date'],
                'שווי': val, 'רווח_דולרי': pnl_usd, 'רווח_אחוז': pnl_pct
            })
        live_df = pd.DataFrame(results)

    # --- SIDEBAR (ניהול חשבון) ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי (דינמי)", f"${current_cash_calc:,.2f}")
    
    total_val = market_val_total + current_cash_calc
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.write("### שווי תיק כולל")
    st.sidebar.write(f"## ${total_val:,.2f}")
    
    color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{color}; font-size: 20px; font-weight: bold; margin-top:-10px;'>{'+' if diff >= 0 else ''}{diff:,.2f}$</p>", unsafe_allow_html=True)
    
    st.sidebar.write("📉 **עמלות מצטברות:**")
    st.sidebar.markdown(f"<p style='color:#ff4b4b; font-size: 18px; font-weight: bold; margin-top:-10px;'>-${total_fees_calc:,.2f}</p>", unsafe_allow_html=True)

    # מחשבון טרייד
    st.sidebar.divider()
    with st.sidebar.popover("🧮 מחשבון טרייד", use_container_width=True):
        st.subheader("מחשבון גודל פוזיציה")
        c_entry = st.number_input("מחיר כניסה $", value=0.0, key="calc_entry")
        c_stop = st.number_input("מחיר סטופ $", value=0.0, key="calc_stop")
        if c_entry > c_stop:
            risk_amount = PORTFOLIO_START_VAL * 0.01 # סיכון של 1% מהתיק
            qty_calc = int(risk_amount / (c_entry - c_stop))
            st.success(f"כמות מניות: {qty_calc} | עלות: ${qty_calc*c_entry:,.2f}")

    # פוזיציות ב-Sidebar
    if not open_trades.empty:
        st.sidebar.subheader("📈 פוזיציות (Live)")
        for _, row in live_df.iterrows():
            p_color = "#00c853" if row['רווח_דולרי'] >= 0 else "#ff4b4b"
            st.sidebar.write(f"**{row['Ticker']}:** ${row['שווי']:,.2f}")
            st.sidebar.markdown(f"<p style='color:{p_color}; margin-top:-15px;'>{'+' if row['רווח_דולרי'] >= 0 else ''}{row['רווח_דולרי']:,.2f}$ ({row['רווח_אחוז']:.2f}%)</p>", unsafe_allow_html=True)

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    st.link_button("📂 פתח גיליון לעדכון נתונים", SHEET_URL, use_container_width=True)
    
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades.empty:
            view_df = live_df.copy()
            view_df['רווח_אחוז'] = view_df['רווח_אחוז'].map("{:.2f}%".format)
            st.dataframe(view_df.sort_values('שווי', ascending=False), use_container_width=True, hide_index=True)
            
            st.divider()
            # גרף פיזור תיק
            pie_data = pd.concat([live_df[['Ticker', 'שווי']].rename(columns={'שווי': 'Value'}), 
                                 pd.DataFrame([{'Ticker': 'מזומן', 'Value': current_cash_calc}])])
            fig = px.pie(pie_data, values='Value', names='Ticker', hole=0.4, title="פיזור הון בתיק")
            st.plotly_chart(fig, use_container_width=True)
    
    with t2:
        if not closed_trades.empty:
            total_realized = closed_trades['PnL'].sum()
            st.markdown(f"### סך רווח ממומש: <span style='color:{'green' if total_realized >= 0 else 'red'};'>${total_realized:,.2f}</span>", unsafe_allow_html=True)
            st.divider()
            # טבלה עם עמודות רחבות לסיבות
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
    st.error(f"שגיאה בטעינת נתונים: {e}")
