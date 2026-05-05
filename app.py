import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון (כל 15 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=15000, key="datarefresh")

# --- נתוני יסוד (תעדכן כאן אם המזומן משתנה בברוקר) ---
CASH_VAL_USER = 12298.89       # מזומן פנוי בדולר
PORTFOLIO_START_VAL = 44302.55  # שווי התיק המקורי (לחישוב רווח כולל)
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

# חיבור לגיליון
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # קריאת הנתונים מהגיליון
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    
    # ניקוי עמודות
    df['Qty'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(0)
    df['עלות כניסה'] = pd.to_numeric(df['עלות כניסה'], errors='coerce').fillna(0)
    df['Exit_Price'] = pd.to_numeric(df['Exit_Price'], errors='coerce').fillna(0)

    # סינון פוזיציות פתוחות בלבד
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].str.len() > 0)].copy()

    market_val_total = 0
    live_rows = []

    if not open_trades.empty:
        # הורדת מחירים מ-yfinance
        tickers_list = open_trades['Ticker'].unique().tolist()
        data = yf.download(tickers_list, period="1d", progress=False)['Close']

        for _, row in open_trades.iterrows():
            ticker = row['Ticker']
            qty = row['Qty']
            cost_basis = row['עלות כניסה']
            
            try:
                # חילוץ מחיר נוכחי
                if len(tickers_list) > 1:
                    current_price = data[ticker].iloc[-1]
                else:
                    current_price = data.iloc[-1]
                
                if pd.isna(current_price): continue

                current_value = current_price * qty
                market_val_total += current_value
                
                pnl_usd = current_value - cost_basis
                pnl_pct = (pnl_usd / cost_basis * 100) if cost_basis != 0 else 0
                
                live_rows.append({
                    "Ticker": ticker,
                    "כמות": qty,
                    "מחיר כניסה (ממוצע)": f"${(cost_basis/qty):.2f}" if qty != 0 else 0,
                    "מחיר נוכחי": f"${current_price:.2f}",
                    "שווי פוזיציה": current_value,
                    "רווח/הפסד $": pnl_usd,
                    "רווח %": pnl_pct
                })
            except:
                continue

    # --- חישובי סיכום ---
    total_portfolio_now = CASH_VAL_USER + market_val_total
    total_profit_loss = total_portfolio_now - PORTFOLIO_START_VAL
    profit_color = "green" if total_profit_loss >= 0 else "red"

    # --- תצוגת Sidebar ---
    st.sidebar.header("📊 סיכום תיק (LIVE)")
    st.sidebar.metric("מזומן פנוי", f"${CASH_VAL_USER:,.2f}")
    st.sidebar.metric("שווי מניות", f"${market_val_total:,.2f}")
    st.sidebar.divider()
    st.sidebar.subheader("שווי תיק כולל")
    st.sidebar.title(f"${total_portfolio_now:,.2f}")
    st.sidebar.markdown(f"**רווח/הפסד כללי:** <span style='color:{profit_color}; font-size:20px;'>{total_profit_loss:,.2f}$</span>", unsafe_allow_html=True)

    # --- תצוגה ראשית ---
    st.title("יומן המסחר של אבי")
    
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("🔓 פוזיציות פתוחות")
        if live_rows:
            display_df = pd.DataFrame(live_rows)
            st.dataframe(display_df.style.format({
                "שווי פוזיציה": "${:,.2f}",
                "רווח/הפסד $": "${:,.2f}",
                "רווח %": "{:.2f}%"
            }), use_container_width=True, hide_index=True)
        else:
            st.write("אין פוזיציות פתוחות בגיליון.")

    with col2:
        st.subheader("💰 חלוקת נכסים")
        # גרף פאי מתוקן
        pie_df = pd.DataFrame([
            {"נכס": "מזומן פנוי", "ערך": CASH_VAL_USER},
            {"נכס": "מניות בתיק", "ערך": market_val_total}
        ])
        fig = px.pie(pie_df, values='ערך', names='נכס', hole=0.5,
                     color_discrete_sequence=['#2ecc71', '#3498db'])
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"שגיאה בקריאת הנתונים: {e}")
