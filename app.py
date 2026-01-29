import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh
import time

# 1. הגדרות דף ורענון אוטומטי (10 שניות)
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=10000, key=f"classic_restore_{int(time.time())}")

# 2. נתוני בסיס
PORTFOLIO_START_VAL = 44302.55 
SHEET_URL = "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit#gid=0"

# פונקציה לניקוי פסיקים והמרת טקסט למספר (הפתרון לבעיית ה-nan)
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
    # קריאת הנתונים (ttl=0 מבטיח משיכה טרייה בכל רענון)
    df = conn.read(spreadsheet=SHEET_URL, ttl="0")
    df.columns = df.columns.str.strip()
    
    # ניקוי כל העמודות הרלוונטיות מפסיקים וסימנים
    cols_to_clean = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL', 'מזומן_עדכני', 'עמלה']
    for col in cols_to_clean:
        if col in df.columns:
            df[col] = df[col].apply(clean_numeric).fillna(0)

    # --- חישוב מזומן מעמודה N ---
    if 'מזומן_עדכני' in df.columns:
        # לוקח את הערך הראשון בעמודה N (תא N2)
        current_cash = float(df['מזומן_עדכני'].iloc[0])
    else:
        current_cash = 3755.0 # גיבוי למקרה שהעמודה חסרה

    # הפרדה לפתוחות וסגורות
    open_trades = df[(df['Exit_Price'] == 0) & (df['Ticker'].notnull()) & (df['Ticker'] != "")].copy()
    closed_trades = df[df['Exit_Price'] > 0].copy()

    # --- חישוב עמלות מדויק ---
    # אם יש עמודת "עמלה" בגיליון, נסכום אותה. אם לא, נשתמש בנוסחה.
    if 'עמלה' in df.columns and df['עמלה'].sum() != 0:
        total_fees = df['עמלה'].sum()
    else:
        fees_open = open_trades['Qty'].apply(get_fee).sum()
        fees_closed = (closed_trades['Qty'].apply(get_fee).sum() * 2)
        total_fees = fees_open + fees_closed

    # --- נתוני לייב ---
    market_val_total = 0
    live_list = []

    if not open_trades.empty:
        summary = open_trades.groupby('Ticker').agg({'Qty': 'sum', 'עלות כניסה': 'sum'}).reset_index()
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
            live_list.append({'Ticker': t, 'כמות': row['Qty'], 'שווי': val, 'רווח_דולרי': pnl_usd, 'רווח_אחוז': pnl_pct})
        
        live_df = pd.DataFrame(live_list)

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי (N2)", f"${current_cash:,.2f}")
    
    total_val = market_val_total + current_cash
    diff = total_val - PORTFOLIO_START_VAL
    
    st.sidebar.write("### שווי תיק כולל")
    st.sidebar.write(f"## ${total_val:,.2f}")
    
    color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{color}; font-size: 20px; font-weight: bold; margin-top:-10px;'>{'+' if diff >= 0 else ''}{diff:,.2f}$</p>", unsafe_allow_html=True)
    
    st.sidebar.write("📉 **עמלות מצטברות:**")
    st.sidebar.markdown(f"<p style='color:#ff4b4b; font-size: 18px; font-weight: bold; margin-top:-10px;'>-${total_fees:,.2f}</p>", unsafe_allow_html=True)

    # מחשבון טרייד
    st.sidebar.divider()
    with st.sidebar.popover("🧮 מחשבון טרייד", use_container_width=True):
        st.subheader("מחשבון גודל פוזיציה")
        c_entry = st.number_input("כניסה $", value=0.0)
        c_stop = st.number_input("סטופ $", value=0.0)
        if c_entry > c_stop:
            q = int((PORTFOLIO_START_VAL * 0.01) / (c_entry - c_stop))
            st.success(f"כמות: {q} | עלות: ${q*c_entry:,.2f}")

    # פירוט פוזיציות בסיידבר
    if not open_trades.empty:
        st.sidebar.subheader("📈 פוזיציות (Live)")
        for _, row in live_df.iterrows():
            p_color = "#00c853" if row['רווח_דולרי'] >= 0 else "#ff4b4b"
            st.sidebar.write(f"**{row['Ticker']}:** ${row['שווי']:,.2f}")
            st.sidebar.markdown(f"<p style='color:{p_color}; margin-top:-15px;'>{'+' if row['רווח_דולרי'] >= 0 else ''}{row['רווח_דולרי']:,.2f}$ ({row['רווח_אחוז']:.2f}%)</p>", unsafe_allow_html=True)

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    st.link_button("📂 פתח גיליון גוגל שיטס", SHEET_URL)
    
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades.empty:
            df_view = live_df.copy()
            df_view['רווח_אחוז'] = df_view['רווח_אחוז'].map("{:.2f}%".format)
            st.dataframe(df_view.sort_values('שווי', ascending=False), use_container_width=True, hide_index=True)
            st.divider()
            pie_data = pd.concat([live_df[['Ticker', 'שווי']].rename(columns={'שווי': 'Value'}), 
                                 pd.DataFrame([{'Ticker': 'מזומן', 'Value': current_cash}])])
            st.plotly_chart(px.pie(pie_data, values='Value', names='Ticker', hole=0.4), use_container_width=True)

    with t2:
        if not closed_trades.empty:
            realized = closed_trades['PnL'].sum()
            st.markdown(f"### סך רווח ממומש: <span style='color:{'green' if realized >=0 else 'red'};'>${realized:,.2f}</span>", unsafe_allow_html=True)
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL', 'סיבת כניסה', 'סיבת יציאה']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
