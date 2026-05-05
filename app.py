import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון אוטומטי
st.set_page_config(page_title="יומן המסחר של אבי - MASTER", layout="wide")
st_autorefresh(interval=15000, key="datarefresh")

# --- נתוני יסוד (מקור האמת) ---
STARTING_EQUITY = 44302.55 
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit?gid=0#gid=0"

def get_fee(qty):
    """פונקציית עמלה מדויקת (מינימום 3.5$ או לפי כמות מניות)"""
    if qty <= 0: return 0
    return 3.50 + (qty * 0.0078)

# 2. חיבור וקריאת נתונים
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # קריאה נקייה מהגיליון
    df_raw = conn.read(ttl="0")
    df = df_raw.copy()
    df.columns = df.columns.str.strip()
    
    # ניקוי והמרת נתונים נומריים
    for col in ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- לוגיקת "מתכנת על": חישוב תזרים מזומנים (Cash Flow) ---
    
    # א. סך המזומן שיצא על כל הקניות שבוצעו אי פעם + עמלות הקנייה שלהן
    df['buy_fee'] = df['Qty'].apply(get_fee)
    total_spent_on_buys = (df['עלות כניסה'] + df['buy_fee']).sum()
    
    # ב. סך המזומן שחזר לקופה מטריידים שנסגרו
    # נוסחה: (עלות כניסה + PnL ברוטו) - עמלת מכירה
    # ה-PnL בגיליון שלך בדרך כלל כבר מחושב אחרי עמלות, אבל אנחנו נוודא החזר מלא:
    closed_mask = df['Exit_Price'] > 0
    df['sell_fee'] = df[closed_mask]['Qty'].apply(get_fee)
    
    # סכום המכירה ברוטו = עלות כניסה + PnL (לפי הגיליון שלך)
    # הערה: אם ה-PnL בשיטס הוא נטו, אנחנו מחזירים את הכסף שחזר לבנק
    money_returned_from_sales = (df.loc[closed_mask, 'עלות כניסה'] + df.loc[closed_mask, 'PnL']).sum()
    
    # ג. מזומן פנוי נוכחי
    current_cash = STARTING_EQUITY - total_spent_on_buys + money_returned_from_sales

    # --- עיבוד פוזיציות פתוחות (איחוד טיקרים) ---
    open_trades = df[~closed_mask & (df['Ticker'].str.len() > 0)].copy()
    
    market_val_total = 0
    live_list = []

    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({
            'Qty': 'sum', 
            'עלות כניסה': 'sum',
            'buy_fee': 'sum',
            'סיבת כניסה': 'first'
        }).reset_index()
        
        tickers = list(summary['Ticker'].unique())
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        for _, row in summary.iterrows():
            t = row['Ticker']
            try:
                # קבלת מחיר שוק
                price = data[t].dropna().iloc[-1] if len(tickers) > 1 else data.dropna().iloc[-1]
                
                qty = row['Qty']
                total_cost_basis = row['עלות כניסה']
                current_val = price * qty
                market_val_total += current_val
                
                # חישוב רווח לייב נטו (כולל עמלת מכירה עתידית)
                estimated_sell_fee = get_fee(qty)
                pnl_usd = (current_val - total_cost_basis) - row['buy_fee'] - estimated_sell_fee
                
                avg_entry = total_cost_basis / qty if qty != 0 else 0
                pnl_pct = ((price / avg_entry) - 1) * 100 if avg_entry != 0 else 0
                
                live_list.append({
                    'Ticker': t, 'כמות': qty, 'מחיר ממוצע': avg_entry,
                    'מחיר שוק': price, 'שווי פוזיציה': current_val, 
                    'רווח $ (נטו)': pnl_usd, 'רווח %': pnl_pct, 'סיבת כניסה': row['סיבת כניסה']
                })
            except: continue
        
        live_df = pd.DataFrame(live_list)

    # --- חישובי שורה תחתונה ---
    total_portfolio_val = current_cash + market_val_total
    total_pnl_all_time = total_portfolio_val - STARTING_EQUITY

    # --- SIDEBAR: דשבורד ניהולי ---
    st.sidebar.header("💰 ניהול חשבון (MASTER)")
    st.sidebar.metric("מזומן פנוי (Cash)", f"${current_cash:,.2f}")
    st.sidebar.metric("שווי מניות (Live Value)", f"${market_val_total:,.2f}")
    
    st.sidebar.divider()
    st.sidebar.write("### שווי תיק כולל (Net)")
    st.sidebar.write(f"## ${total_portfolio_val:,.2f}")
    
    pnl_color = "#00c853" if total_pnl_all_time >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{pnl_color}; font-size: 20px; font-weight: bold; margin-top:-10px;'>{'+' if total_pnl_all_time >= 0 else ''}{total_pnl_all_time:,.2f}$ (רווח/הפסד כללי)</p>", unsafe_allow_html=True)

    # מחשבון ניהול סיכונים
    st.sidebar.divider()
    st.sidebar.subheader("🧮 מחשבון טרייד (1% סיכון)")
    c_entry = st.sidebar.number_input("מחיר כניסה $", key="calc_entry")
    c_stop = st.sidebar.number_input("מחיר סטופ $", key="calc_stop")
    if c_entry > c_stop > 0:
        risk_sum = total_portfolio_val * 0.01
        qty_to_buy = int(risk_sum / (c_entry - c_stop))
        st.sidebar.success(f"כמות: {qty_to_buy} יח'\n\nחשיפה: ${qty_to_buy*c_entry:,.2f}")

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    st.link_button("📂 פתח גיליון Google Sheets", SHEET_URL)

    t1, t2 = st.tabs(["📈 פוזיציות פתוחות (מאוחד)", "📜 היסטוריית טריידים"])
    
    with t1:
        if not live_list == []:
            def color_pnl(val): return f'color: {"green" if val > 0 else "red"}'
            st.dataframe(live_df.style.map(color_pnl, subset=['רווח $ (נטו)', 'רווח %'])\
                         .format({'מחיר ממוצע': "{:.2f}$", 'מחיר שוק': "{:.2f}$", 'שווי פוזיציה': "{:,.2f}$", 'רווח $ (נטו)': "{:,.2f}$", 'רווח %': "{:.2f}%"}), 
                         use_container_width=True, hide_index=True)
            
            st.divider()
            # גרף פיזור נכסים
            pie_data = pd.concat([live_df[['Ticker', 'שווי פוזיציה']].rename(columns={'שווי פוזיציה': 'Value'}), 
                                 pd.DataFrame([{'Ticker': 'מזומן פנוי', 'Value': current_cash}])])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Ticker', hole=0.4, 
                                   title="פיזור הון כולל (Asset Allocation)"), use_container_width=True)
        else:
            st.info("אין פוזיציות פתוחות ביומן.")

    with t2:
        if closed_mask.any():
            st.metric("סך רווח ממומש (נטו)", f"${df.loc[closed_mask, 'PnL'].sum():,.2f}")
            st.dataframe(df[closed_mask][['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL']].sort_values('Exit_Date', ascending=False), 
                         use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה קריטית בעיבוד הנתונים: {e}")
