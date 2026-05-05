import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון אוטומטי
st.set_page_config(page_title="יומן המסחר של אבי - PRO", layout="wide")
st_autorefresh(interval=15000, key="datarefresh")

# --- הגדרת עוגן הון (הסכום היחיד שאינו משתנה) ---
STARTING_EQUITY = 44302.55 
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

# 2. חיבור לנתונים
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    
    # ניקוי עמודות נומריות
    for col in ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- לוגיקת מתכנת: חישוב מזומן פנוי (Cash Flow Logic) ---
    
    # א. סך כל הכסף שיצא מהחשבון על קניות (כל השורות בגיליון)
    total_money_spent = df['עלות כניסה'].sum()
    
    # ב. סך כל הכסף שחזר לחשבון ממכירות (רק טריידים סגורים)
    # כסף חוזר = עלות הקנייה המקורית + הרווח/הפסד (PnL)
    closed_trades_mask = df['Exit_Price'] > 0
    money_returned = (df.loc[closed_trades_mask, 'עלות כניסה'] + df.loc[closed_trades_mask, 'PnL']).sum()
    
    # ג. המזומן הפנוי האמיתי
    current_cash = STARTING_EQUITY - total_money_spent + money_returned

    # --- עיבוד פוזיציות פתוחות ---
    open_trades = df[~closed_trades_mask & (df['Ticker'].str.len() > 0)].copy()
    
    market_val_total = 0
    live_list = []

    if not open_trades.empty:
        # איחוד פוזיציות לפי טיקר
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum', 'סיבת כניסה': 'first'}).reset_index()
        tickers = list(summary['Ticker'].unique())
        
        # הורדה מהירה של נתוני שוק
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        for _, row in summary.iterrows():
            t = row['Ticker']
            try:
                price = data[t].dropna().iloc[-1] if len(tickers) > 1 else data.dropna().iloc[-1]
                val = price * row['Qty']
                market_val_total += val
                
                cost = row['עלות כניסה']
                avg_entry = cost / row['Qty'] if row['Qty'] != 0 else 0
                pnl_usd = (val - cost) - get_fee(row['Qty'])
                pnl_pct = ((price / avg_entry) - 1) * 100 if avg_entry != 0 else 0
                
                live_list.append({
                    'Ticker': t, 'כמות': row['Qty'], 'מחיר ממוצע': avg_entry,
                    'מחיר שוק': price, 'שווי פוזיציה': val, 'רווח $': pnl_usd, 
                    'רווח %': pnl_pct, 'סיבת כניסה': row['סיבת כניסה']
                })
            except: continue
        
        live_df = pd.DataFrame(live_list)

    # --- שורה תחתונה ---
    total_portfolio_val = current_cash + market_val_total
    total_pnl_all_time = total_portfolio_val - STARTING_EQUITY

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון (Auto-Calc)")
    st.sidebar.metric("מזומן פנוי (Cash)", f"${current_cash:,.2f}")
    st.sidebar.metric("שווי מניות (Market)", f"${market_val_total:,.2f}")
    
    st.sidebar.divider()
    st.sidebar.write("### שווי תיק כולל (Live)")
    st.sidebar.write(f"## ${total_portfolio_val:,.2f}")
    
    color = "#00c853" if total_pnl_all_time >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{color}; font-size: 20px; font-weight: bold; margin-top:-10px;'>{'+' if total_pnl_all_time >= 0 else ''}{total_pnl_all_time:,.2f}$</p>", unsafe_allow_html=True)

    # מחשבון טרייד (1% סיכון)
    st.sidebar.divider()
    st.sidebar.subheader("🧮 מחשבון טרייד")
    c_entry = st.sidebar.number_input("מחיר כניסה $", value=0.0)
    c_stop = st.sidebar.number_input("מחיר סטופ $", value=0.0)
    if c_entry > c_stop > 0:
        q = int((total_portfolio_val * 0.01) / (c_entry - c_stop))
        st.sidebar.success(f"כמות: {q} יח' | עלות: ${q*c_entry:,.2f}")

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    st.link_button("📂 פתח גיליון Google Sheets", SHEET_URL)

    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות (מאוחד)", "🔒 טריידים סגורים"])
    
    with t1:
        if live_list:
            def color_pnl(val): return f'color: {"green" if val > 0 else "red"}'
            st.dataframe(live_df.style.map(color_pnl, subset=['רווח $', 'רווח %'])\
                         .format({'מחיר ממוצע': "{:.2f}$", 'מחיר שוק': "{:.2f}$", 'שווי פוזיציה': "{:,.2f}$", 'רווח $': "{:,.2f}$", 'רווח %': "{:.2f}%"}), 
                         use_container_width=True, hide_index=True)
            
            # גרף פאי
            pie_data = pd.concat([live_df[['Ticker', 'שווי פוזיציה']].rename(columns={'שווי פוזיציה': 'Value'}), 
                                 pd.DataFrame([{'Ticker': 'מזומן', 'Value': current_cash}])])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Ticker', hole=0.4, title="פיזור הון"), use_container_width=True)

    with t2:
        if not closed_trades_mask.any():
            st.info("אין טריידים סגורים.")
        else:
            st.metric("רווח ממומש", f"${df.loc[closed_trades_mask, 'PnL'].sum():,.2f}")
            st.dataframe(df[closed_trades_mask][['Ticker', 'Entry_Date', 'Exit_Date', 'PnL']].sort_values('Exit_Date', ascending=False), use_container_width=True)

except Exception as e:
    st.error(f"שגיאה קריטית: {e}")
