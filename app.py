import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh
import time

# 1. הגדרות דף ורענון אוטומטי
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key=f"baseline_v1_{int(time.time())}")

# 2. נתוני בסיס
PORTFOLIO_START_VAL = 44302.55 
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit#gid=0"

def clean_numeric(val):
    if pd.isna(val): return 0.0
    if isinstance(val, str):
        val = val.replace(',', '').replace('$', '').strip()
    return pd.to_numeric(val, errors='coerce')

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

# 3. חיבור לגיליון
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(spreadsheet=SHEET_URL, ttl="0")
    df.columns = df.columns.str.strip()
    
    cols_to_clean = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL', 'מזומן_עדכני', 'עמלה']
    for col in cols_to_clean:
        if col in df.columns:
            df[col] = df[col].apply(clean_numeric).fillna(0)

    # משיכת מזומן
    current_cash = float(df['מזומן_עדכני'].iloc[0]) if 'מזומן_עדכני' in df.columns else 0.0

    # הפרדה לפתוחות וסגורות
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # עמלות
    if 'עמלה' in df.columns and df['עמלה'].sum() != 0:
        total_fees = df['עמלה'].sum()
    else:
        total_fees = open_trades['Qty'].apply(get_fee).sum() + (closed_trades['Qty'].apply(get_fee).sum() * 2)

    # נתוני לייב
    market_val_total = 0
    live_df = pd.DataFrame()

    if not open_trades.empty:
        # שמירת "סיבת כניסה" עבור כל טיקר (לוקח את הראשונה שנמצאה)
        reasons = open_trades.groupby('Ticker')['סיבת כניסה'].first().to_dict()
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum'}).reset_index()
        tickers = list(summary['Ticker'].unique())
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        live_list = []
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
                'שווי שוק': val, 
                'רווח $': pnl_usd, 
                'רווח %': pnl_pct,
                'סיבת כניסה': reasons.get(t, "")
            })
        live_df = pd.DataFrame(live_list)

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${current_cash:,.2f}")
    
    total_val = market_val_total + current_cash
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.subheader("שווי תיק כולל")
    st.sidebar.title(f"${total_val:,.2f}")
    
    pnl_color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{pnl_color}; font-size: 20px; font-weight: bold; margin-top:-10px;'>{'+' if diff >= 0 else ''}{diff:,.2f}$</p>", unsafe_allow_html=True)
    st.sidebar.write(f"📉 **עמלות:** ${total_fees:,.2f}")

    # מחשבון טרייד מוטמע (אינליין)
    st.sidebar.divider()
    st.sidebar.subheader("🧮 מחשבון טרייד")
    calc_name = st.sidebar.text_input("שם המניה", placeholder="למשל: NVDA")
    c_entry = st.sidebar.number_input("מחיר כניסה $", value=0.0)
    c_stop = st.sidebar.number_input("מחיר סטופ $", value=0.0)
    if c_entry > c_stop:
        q = int((PORTFOLIO_START_VAL * 0.01) / (c_entry - c_stop))
        st.sidebar.success(f"**{calc_name}**\n\nכמות: {q} יחידות\n\nעלות: ${q*c_entry:,.2f}")

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    st.link_button("📂 פתח גיליון גוגל שיטס", SHEET_URL)
    
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not live_df.empty:
            # פונקציית עיצוב צבעים לטבלה
            def style_pnl(v):
                color = 'green' if v > 0 else 'red'
                return f'color: {color}; font-weight: bold'

            # יצירת תצוגה מעוצבת
            df_display = live_df.copy()
            styled_df = df_display.style.format({
                'שווי שוק': '${:,.2f}',
                'רווח $': '${:,.2f}',
                'רווח %': '{:.2f}%'
            }).applymap(style_pnl, subset=['רווח $', 'רווח %'])

            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            st.divider()
            pie_data = pd.concat([live_df[['Ticker', 'שווי שוק']].rename(columns={'שווי שוק': 'Value'}), 
                                 pd.DataFrame([{'Ticker': 'מזומן', 'Value': current_cash}])])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Ticker', hole=0.4, title="פיזור הון"), use_container_width=True)

    with t2:
        if not closed_trades.empty:
            realized = closed_trades['PnL'].sum()
            st.markdown(f"### סך רווח ממומש: <span style='color:{'green' if realized >=0 else 'red'};'>${realized:,.2f}</span>", unsafe_allow_html=True)
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL', 'סיבת כניסה', 'סיבת יציאה']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה בחיבור: {e}")
