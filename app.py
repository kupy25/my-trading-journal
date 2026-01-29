import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import time

# 1. הגדרות דף ורענון (10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key=f"trading_live_{int(time.time())}")

# 2. קישורים
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit#gid=0"
CSV_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/export?format=csv&gid=0"
PORTFOLIO_START_VAL = 44302.55 

st.markdown(f"### [🔗 מעבר לגיליון גוגל שיטס]({SHEET_URL})")

try:
    # 3. קריאה וניקוי נתונים (כולל הפסיקים שסידרנו)
    df = pd.read_csv(f"{CSV_URL}&t={int(time.time())}")
    df.columns = df.columns.str.strip()

    def clean_num(val):
        if pd.isna(val): return 0.0
        if isinstance(val, str):
            val = val.replace(',', '').replace('$', '').strip()
        return pd.to_numeric(val, errors='coerce')

    for col in ['Qty', 'עלות כניסה', 'Exit_Price', 'PnL', 'מזומן_עדכני']:
        if col in df.columns:
            df[col] = df[col].apply(clean_num).fillna(0.0)

    # 4. מזומן ופוזיציות
    current_cash = float(df['מזומן_עדכני'].iloc[0]) if 'מזומן_עדכני' in df.columns else 0.0
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    market_val_total = 0
    live_df = pd.DataFrame()

    if not open_trades.empty:
        # איחוד שורות של אותו טיקר (למשל BITB)
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum'}).reset_index()
        tickers = summary['Ticker'].tolist()
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        results = []
        for _, row in summary.iterrows():
            t = row['Ticker']
            price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            val = float(price * row['Qty'])
            market_val_total += val
            p_usd = val - row['עלות כניסה']
            p_pct = (p_usd / row['עלות כניסה']) * 100
            results.append({
                'Ticker': t, 
                'כמות': f"{row['Qty']:.2f}",
                'שווי שוק': val, 
                'רווח/הפסד $': p_usd,
                'רווח/הפסד %': p_pct
            })
        live_df = pd.DataFrame(results)

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${current_cash:,.2f}")
    
    total_val = market_val_total + current_cash
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.subheader("שווי תיק כולל")
    st.sidebar.title(f"${total_val:,.2f}")
    
    color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<h3 style='color:{color};'>{'+' if diff >= 0 else ''}{diff:,.2f}$</h3>", unsafe_allow_html=True)

    # --- תצוגה ראשית ---
    st.subheader("פוזיציות פתוחות")
    if not live_df.empty:
        # עיצוב הטבלה עם צבעים
        def color_pnl(val):
            color = 'green' if val > 0 else 'red'
            return f'color: {color}'

        styled_df = live_df.style.format({
            'שווי שוק': '${:,.2f}',
            'רווח/הפסד $': '${:,.2f}',
            'רווח/הפסד %': '{:.2f}%'
        }).applymap(color_pnl, subset=['רווח/הפסד $', 'רווח/הפסד %'])
        
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        # גרף פאי
        pie_data = pd.concat([
            live_df[['Ticker', 'שווי שוק']].rename(columns={'שווי שוק': 'שווי'}), 
            pd.DataFrame([{'Ticker': 'מזומן', 'שווי': current_cash}])
        ])
        fig = px.pie(pie_data, values='שווי', names='Ticker', hole=0.4, 
                     color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig, use_container_width=True)

    # טריידים סגורים
    with st.expander("🔒 לצפייה בטריידים סגורים"):
        if not closed_trades.empty:
            st.write(f"### רווח ממומש כולל: ${closed_trades['PnL'].sum():,.2f}")
            st.dataframe(closed_trades[['Ticker', 'Qty', 'PnL', 'Exit_Date']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
