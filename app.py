import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import time

# 1. הגדרות דף ורענון
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key=f"classic_v3_{int(time.time())}")

# 2. הגדרות קבועות
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit#gid=0"
CSV_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/export?format=csv&gid=0"
PORTFOLIO_START_VAL = 44302.55 

# פונקציה לניקוי פסיקים והמרה למספר (התיקון הקריטי)
def clean_num(val):
    if pd.isna(val): return 0.0
    if isinstance(val, str):
        val = val.replace(',', '').replace('$', '').strip()
    return pd.to_numeric(val, errors='coerce')

# --- כותרת וכפתור גיליון ---
st.title("📊 יומן המסחר של אבי")
st.link_button("📂 פתח גיליון גוגל שיטס", SHEET_URL)
st.divider()

try:
    # 3. טעינת נתונים
    df = pd.read_csv(f"{CSV_URL}&t={int(time.time())}")
    df.columns = df.columns.str.strip()

    # המרת כל העמודות הרלוונטיות
    cols_to_fix = ['Qty', 'עלות כניסה', 'Exit_Price', 'PnL', 'מזומן_עדכני', 'עמלה']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = df[col].apply(clean_num).fillna(0.0)

    # 4. משיכת נתונים בסיסיים
    current_cash = float(df['מזומן_עדכני'].iloc[0]) if 'מזומן_עדכני' in df.columns else 0.0
    total_fees = df['עמלה'].sum() if 'עמלה' in df.columns else 0.0
    
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # 5. עיבוד פוזיציות פתוחות
    market_val_total = 0
    live_df = pd.DataFrame()

    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum'}).reset_index()
        tickers = summary['Ticker'].tolist()
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        res = []
        for _, row in summary.iterrows():
            t = row['Ticker']
            price = data[t].iloc[-1] if len(tickers) > 1 else data.iloc[-1]
            val = float(price * row['Qty'])
            market_val_total += val
            res.append({
                'Ticker': t, 
                'כמות': row['Qty'], 
                'שווי שוק': val, 
                'רווח/הפסד $': val - row['עלות כניסה']
            })
        live_df = pd.DataFrame(res)

    # --- SIDEBAR (ניהול חשבון) ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${current_cash:,.2f}")
    
    total_portfolio_val = market_val_total + current_cash
    total_diff = total_portfolio_val - PORTFOLIO_START_VAL
    
    st.sidebar.subheader("שווי תיק כולל")
    st.sidebar.title(f"${total_portfolio_val:,.2f}")
    
    color = "#00c853" if total_diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<h3 style='color:{color};'>{'+' if total_diff >= 0 else ''}{total_diff:,.2f}$</h3>", unsafe_allow_html=True)
    
    st.sidebar.divider()
    st.sidebar.metric("סך עמלות ששולמו", f"${total_fees:,.2f}")

    # --- מחשבון טרייד בסיידבר ---
    st.sidebar.divider()
    st.sidebar.subheader("🧮 מחשבון טרייד מהיר")
    calc_ticker = st.sidebar.text_input("טיקר", "AAPL")
    calc_qty = st.sidebar.number_input("כמות", min_value=0.0, value=10.0)
    calc_price = st.sidebar.number_input("מחיר כניסה", min_value=0.0, value=150.0)
    st.sidebar.write(f"עלות טרייד: **${calc_qty * calc_price:,.2f}**")

    # --- לשוניות בדף הראשי ---
    tab1, tab2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])

    with tab1:
        if not live_df.empty:
            st.dataframe(live_df.style.format({'שווי שוק': '${:,.2f}', 'רווח/הפסד $': '${:,.2f}'}), 
                         use_container_width=True, hide_index=True)
            
            st.divider()
            # גרף פאי
            pie_data = pd.concat([
                live_df[['Ticker', 'שווי שוק']].rename(columns={'שווי שוק': 'שווי'}), 
                pd.DataFrame([{'Ticker': 'CASH', 'שווי': current_cash}])
            ])
            fig = px.pie(pie_data, values='שווי', names='Ticker', hole=0.4, title="פיזור הון בתיק")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("אין פוזיציות פתוחות כרגע.")

    with tab2:
        if not closed_trades.empty:
            st.write(f"### רווח ממומש מצטבר: ${closed_trades['PnL'].sum():,.2f}")
            st.dataframe(closed_trades[['Ticker', 'Qty', 'Entry_Price', 'Exit_Price', 'PnL']], 
                         use_container_width=True, hide_index=True)
        else:
            st.info("אין טריידים סגורים בהיסטוריה.")

except Exception as e:
    st.error(f"שגיאה בטעינת הנתונים: {e}")
