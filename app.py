import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק ומעקב טריידים - 2026")

# --- הגדרות הון ומזומן (Sidebar) ---
st.sidebar.header("⚙️ ניהול מזומן והון")
initial_total_value = 44302.55 # שווי ב-31.12.2025 לפי TradeStation

# שדה מזומן מדויק עם שתי ספרות עשרוניות
available_cash = st.sidebar.number_input(
    "מזומן פנוי בחשבון ($)", 
    value=5732.40, 
    step=0.01, 
    format="%.2f"
)

# חיבור ל-Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_trades = conn.read(ttl="0")
    
    if df_trades is not None and not df_trades.empty:
        df_trades.columns = df_trades.columns.str.strip()
        for col in ['Entry_Price', 'Qty', 'Exit_Price', 'PnL']:
            if col in df_trades.columns:
                df_trades[col] = pd.to_numeric(df_trades[col], errors='coerce').fillna(0)

        stock_value_on_paper = 0
        total_unrealized_pnl = 0
        
        # חישוב שווי פוזיציות פתוחות
        open_trades = df_trades[df_trades['Exit_Price'] == 0]
        if not open_trades.empty:
            st.sidebar.divider()
            st.sidebar.subheader("שווי פוזיציות פתוחות")
            for index, row in open_trades.iterrows():
                ticker = str(row['Ticker'])
                if ticker and ticker != 'nan' and ticker != "":
                    try:
                        stock = yf.Ticker(ticker)
                        ticker_data = stock.history(period="1d")
                        if not ticker_data.empty:
                            curr_price = ticker_data['Close'].iloc[-1]
                            current_pos_value = curr_price * row['Qty']
                            stock_value_on_paper += current_pos_value
                            
                            pnl_open = (curr_price - row['Entry_Price']) * row['Qty']
                            
                            # תיקון תצוגת הצבעים ב-Sidebar
                            label = f"**{ticker}:** {current_pos_value:,.2f}$"
                            st.sidebar.write(label)
                            if pnl_open >= 0:
                                st.sidebar.caption(f":green[+{pnl_open:,.2f}$]")
                            else:
                                st.sidebar.caption(f":red[{pnl_open:,.2f}$]")
                    except:
                        continue

        # חישוב שווי תיק כולל
        total_portfolio_value = stock_value_on_paper + available_cash
        diff_from_start = total_portfolio_value - initial_total_value
        
        st.sidebar.divider()
        st.sidebar.metric(
            label="שווי תיק כולל (Cash + Stocks)", 
            value=f"${total_portfolio_value:,.2f}", 
            delta=f"${diff_from_start:,.2f}",
            delta_color="normal" if diff_from_start >= 0 else "inverse"
        )
        
        st.sidebar.write(f"📈 שווי מניות (Market): ${stock_value_on_paper:,.2f}")
        st.sidebar.write(f"💵 מזומן פנוי: ${available_cash:,.2f}")

        # ממשק פעולות
        st.header("➕ פעולות")
        st.link_button("עדכן טריידים בגיליון גוגל", "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit")

        # טבלת טריידים
        st.subheader("🗂️ יומן טריידים מלא")
        st.dataframe(df_trades, use_container_width=True)

        # תחקור טכני
        st.subheader("🔍 תחקור טכני Live")
        unique_tickers = [t for t in df_trades['Ticker'].unique() if pd.notna(t) and t != ""]
        for ticker in unique_tickers:
            try:
                stock = yf.Ticker(str(ticker))
                hist = stock.history(period="1y")
                if not hist.empty:
                    curr = hist['Close'].iloc[-1]
                    ma150 = hist['Close'].rolling(window=150).mean().iloc[-1]
                    
                    with st.expander(f"ניתוח {ticker}"):
                        c1, c2 = st.columns([1, 2])
                        with c1:
                            if curr > ma150:
                                st.success("מעל 150 MA ✅")
                            else:
                                st.error("מתחת ל-150 MA ❌")
                            st.write(f"מחיר: {curr:.2f}$ | ממוצע: {ma150:.2f}$")
                        with c2:
                            st.line_chart(hist['Close'].tail(60))
            except:
                continue
    else:
        st.info("הגיליון ריק. הוסף טריידים בגיליון גוגל.")

except Exception as e:
    st.error(f"שגיאה במערכת: {e}")
