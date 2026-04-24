import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. הגדרות דף ורענון אוטומטי
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st_autorefresh(interval=15000, key="datarefresh")

# הגדרת שווי התחלה
PORTFOLIO_START_VAL = 44302.55 

def get_fee(qty):
    return 3.50 + (qty * 0.0078) if qty > 0 else 0

# 2. חיבור וקריאת נתונים
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
    df.columns = df.columns.str.strip()
    
    # ניקוי נתונים נומריים - המרה בטוחה למספרים
    numeric_cols = ['Qty', 'Entry_Price', 'Exit_Price', 'עלות כניסה', 'PnL', 'מזומן_עדכני']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # שליפת המזומן העדכני - טיפול בטוח בערכים ריקים (פותר את שגיאת ה-NA)
    if 'מזומן_עדכני' in df.columns:
        valid_cash = df[df['מזומן_עדכני'] > 0]['מזומן_עדכני']
        current_cash = float(valid_cash.iloc[-1]) if not valid_cash.empty else 0.0
    else:
        current_cash = 0.0

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
        # הורדת נתונים מ-Yahoo Finance
        data = yf.download(tickers, period="1d", progress=False)['Close']
        
        for _, row in summary.iterrows():
            t = row['Ticker']
            try:
                # חילוץ מחיר אחרון בצורה בטוחה
                if len(tickers) > 1:
                    price = data[t].dropna().iloc[-1]
                else:
                    price = data.dropna().iloc[-1]
                
                val = price * row['Qty']
                market_val_total += val
                
                avg_cost = row['עלות כניסה'] / row['Qty'] if row['Qty'] != 0 else 0
                pnl_usd = (val - row['עלות כניסה']) - get_fee(row['Qty'])
                pnl_pct = ((price - avg_cost) / avg_cost) * 100 if avg_cost != 0 else 0
                
                live_list.append({
                    'Ticker': t, 
                    'כמות': row['Qty'], 
                    'שווי': val, 
                    'רווח $': pnl_usd, 
                    'רווח %': pnl_pct,
                    'סיבת כניסה': row['סיבת כניסה']
                })
            except:
                continue
        
        live_df = pd.DataFrame(live_list)

    # --- SIDEBAR ---
    st.sidebar.header("⚙️ ניהול חשבון")
    st.sidebar.metric("מזומן פנוי", f"${current_cash:,.2f}")
    
    total_portfolio_val = market_val_total + current_cash
    diff = total_portfolio_val - PORTFOLIO_START_VAL
    
    st.sidebar.write("### שווי תיק כולל")
    st.sidebar.write(f"## ${total_portfolio_val:,.2f}")
    
    color = "#00c853" if diff >= 0 else "#ff4b4b"
    st.sidebar.markdown(f"<p style='color:{color}; font-size: 20px; font-weight: bold; margin-top:-10px;'>{'+' if diff >= 0 else ''}{diff:,.2f}$</p>", unsafe_allow_html=True)
    
    st.sidebar.write("📉 **עמלות מצטברות:**")
    st.sidebar.markdown(f"<p style='color:#ff4b4b; font-size: 18px; font-weight: bold; margin-top:-10px;'>-${total_fees:,.2f}</p>", unsafe_allow_html=True)

    # מחשבון טרייד
    st.sidebar.divider()
    st.sidebar.subheader("🧮 מחשבון טרייד")
    calc_ticker = st.sidebar.text_input("סימול מניה", value="AAPL")
    c_entry = st.sidebar.number_input("מחיר כניסה $", value=0.0)
    c_stop = st.sidebar.number_input("מחיר סטופ $", value=0.0)
    
    if c_entry > c_stop and c_stop > 0:
        risk_amount = PORTFOLIO_START_VAL * 0.01
        q = int(risk_amount / (c_entry - c_stop))
        st.sidebar.success(f"מניה: {calc_ticker}\n\nכמות: {q} יח'\n\nעלות: ${q*c_entry:,.2f}")

    # --- מסך ראשי ---
    st.title("📊 יומן המסחר של אבי")
    
    t1, t2 = st.tabs(["🔓 פוזיציות פתוחות", "🔒 טריידים סגורים"])
    
    with t1:
        if not open_trades.empty and not live_df.empty:
            # פונקציית צביעה
            def color_pnl(val):
                color = 'green' if val > 0 else 'red'
                return f'color: {color}'

            styled_df = live_df.style.map(color_pnl, subset=['רווח $', 'רווח %'])\
                                     .format({'שווי': "{:,.2f}$", 'רווח $': "{:,.2f}$", 'רווח %': "{:.2f}%"})
            
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            st.divider()
            pie_data = pd.concat([
                live_df[['Ticker', 'שווי']].rename(columns={'שווי': 'Value'}), 
                pd.DataFrame([{'Ticker': 'מזומן', 'Value': current_cash}])
            ])
            fig = px.pie(pie_data, values='Value', names='Ticker', hole=0.4, title="חלוקת נכסים")
            st.plotly_chart(fig, use_container_width=True)

    with t2:
        if not closed_trades.empty:
            closed_trades['Exit_Date'] = pd.to_datetime(closed_trades['Exit_Date'], errors='coerce')
            current_year = pd.Timestamp.now().year
            ytd_trades = closed_trades[closed_trades['Exit_Date'].dt.year == current_year]
            ytd_realized = ytd_trades['PnL'].sum()
            total_realized = closed_trades['PnL'].sum()
            
            c1, c2 = st.columns(2)
            c1.metric("רווח ממומש (כללי)", f"${total_realized:,.2f}")
            c2.metric(f"רווח ממומש {current_year}", f"${ytd_realized:,.2f}")
            
            st.divider()
            st.dataframe(closed_trades[['Ticker', 'Entry_Date', 'Exit_Date', 'Qty', 'PnL', 'סיבת כניסה', 'סיבת יציאה']].sort_values('Exit_Date', ascending=False), 
                         use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"שגיאה בעיבוד הנתונים: {e}")
