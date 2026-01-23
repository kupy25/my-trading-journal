import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק ומעקב טריידים - 2026")

# --- נתוני יסוד לפי TradeStation ---
initial_value_dec_25 = 44302.55 #
st.sidebar.header("⚙️ נתוני חשבון")
available_cash = st.sidebar.number_input("מזומן פנוי בחשבון ($)", value=5732.40, step=0.01, format="%.2f") #

conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_trades = conn.read(ttl="0")
    if df_trades is not None and not df_trades.empty:
        df_trades.columns = df_trades.columns.str.strip()
        for col in ['Entry_Price', 'Qty', 'Exit_Price', 'PnL']:
            if col in df_trades.columns:
                df_trades[col] = pd.to_numeric(df_trades[col], errors='coerce').fillna(0)

        # הפרדת טריידים
        closed_trades = df_trades[df_trades['Exit_Price'] > 0].copy()
        open_trades = df_trades[df_trades['Exit_Price'] == 0].copy()

        # --- משיכת נתונים קבוצתית (מונע שגיאות טעינה) ---
        open_tickers = [str(t).strip().upper() for t in open_trades['Ticker'].dropna().unique() if str(t).strip()]
        
        market_data = {}
        if open_tickers:
            with st.spinner('מושך נתוני שוק עדכניים...'):
                # משיכה של כל הטיקרים יחד (הרבה יותר אמין)
                data_download = yf.download(open_tickers, period="1y", group_by='ticker', progress=False)
                for ticker in open_tickers:
                    try:
                        if len(open_tickers) > 1:
                            t_hist = data_download[ticker]
                        else:
                            t_hist = data_download
                        
                        if not t_hist.empty:
                            market_data[ticker] = {
                                'curr': t_hist['Close'].iloc[-1],
                                'ma150': t_hist['Close'].rolling(window=150).mean().iloc[-1],
                                'hist': t_hist
                            }
                    except: continue

        # --- Sidebar: שווי פוזיציות ו-Unrealized P/L ---
        market_value_stocks = 0
        total_unrealized_pnl = 0 

        if not open_trades.empty:
            st.sidebar.divider()
            st.sidebar.subheader("פוזיציות פתוחות (Live)")
            for _, row in open_trades.iterrows():
                t = str(row['Ticker']).strip().upper()
                if t in market_data:
                    curr_p = market_data[t]['curr']
                    pos_val = curr_p * row['Qty']
                    market_value_stocks += pos_val
                    pnl_open = (curr_p - row['Entry_Price']) * row['Qty']
                    total_unrealized_pnl += pnl_open
                    
                    st.sidebar.write(f"**{t}:** {pos_val:,.2f}$")
                    if pnl_open >= 0:
                        st.sidebar.write(f":green[▲ +{pnl_open:,.2f}$]")
                    else:
                        st.sidebar.write(f":red[▼ {pnl_open:,.2f}$]")

            # תצוגת Unrealized P/L נקייה ללא HTML
            st.sidebar.divider()
            st.sidebar.write("### Unrealized P/L")
            if total_unrealized_pnl >= 0:
                st.sidebar.success(f"${total_unrealized_pnl:,.2f}")
            else:
                st.sidebar.error(f"${total_unrealized_pnl:,.2f}")

        # חישוב שווי כולל ודלתא מהפתיחה
        total_value_now = market_value_stocks + available_cash
        diff = total_value_now - initial_value_dec_25

        st.sidebar.divider()
        st.sidebar.write("### שווי תיק כולל")
        st.sidebar.write(f"## ${total_value_now:,.2f}")
        
        # תיקון חץ אדום להפסד
        color = "#ff4b4b" if diff < 0 else "#00c853"
        icon, label = ("▼", "הפסד מתחילת השנה") if diff < 0 else ("▲", "רווח מתחילת השנה")
        st.sidebar.markdown(f"""<div style="border: 1px solid {color}; border-radius: 5px; padding: 10px; background-color: rgba(0,0,0,0.05);">
                <p style="margin: 0; font-size: 14px; color: gray;">{label}</p>
                <h3 style="margin: 0; color: {color};">{icon} ${abs(diff):,.2f}</h3>
            </div>""", unsafe_allow_html=True)

        # --- תצוגה מרכזית ---
        st.header("🔄 ניהול פוזיציות")
        st.link_button("📂 פתח גיליון גוגל לעדכון", "https://docs.google.com/spreadsheets/d/11lxQ5QH3NbgwUQZ18ARrpYaHCGPdxF6o9vJvPf0Anpg/edit")

        tab1, tab2 = st.tabs(["🔓 טריידים פתוחים", "🔒 טריידים סגורים"])
        with tab1:
            st.subheader("פוזיציות פעילות")
            st.dataframe(open_trades, use_container_width=True)
            st.divider()
            st.subheader("🔍 תחקור טכני (פוזיציות פתוחות)")
            
            for t in open_tickers:
                if t in market_data:
                    curr = market_data[t]['curr']
                    ma150 = market_data[t]['ma150']
                    
                    with st.expander(f"ניתוח {t}"):
                        c1, c2 = st.columns([1, 2])
                        with c1:
                            if curr > ma150: st.success("מגמה חיובית (מעל 150 MA) ✅")
                            else: st.error("מגמה שלילית (מתחת ל-150 MA) ❌")
                            st.write(f"**מחיר:** {curr:.2f}$ | **150 MA:** {ma150:.2f}$")
                        with c2:
                            st.line_chart(market_data[t]['hist']['Close'].tail(60))
                else:
                    st.warning(f"לא ניתן למשוך נתונים עבור {t} כרגע.")

        with tab2:
            st.subheader("היסטוריית עסקאות (YTD Loss: $1,916.05)") #
            st.dataframe(closed_trades, use_container_width=True)

except Exception as e:
    st.error(f"שגיאה בטעינה: {e}")
