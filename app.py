import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
import datetime

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק ומחשבון סיכונים - 2026")

# --- נתוני יסוד ---
initial_value_dec_25 = 44302.55
st.sidebar.header("⚙️ נתוני חשבון")
available_cash = st.sidebar.number_input("מזומן פנוי בחשבון ($)", value=5732.40, step=0.01)

# --- מחשבון גודל פוזיציה חדשה ---
st.sidebar.divider()
st.sidebar.subheader("🧮 מחשבון טרייד חדש")
calc_ticker = st.sidebar.text_input("טיקר למחשבון", value="").strip().upper()
entry_p = st.sidebar.number_input("מחיר כניסה מתוכנן ($)", min_value=0.0, step=0.1)
stop_p = st.sidebar.number_input("סטופ לוס מתוכנן ($)", min_value=0.0, step=0.1)
risk_pct = st.sidebar.slider("סיכון מהתיק (%)", 0.5, 3.0, 1.0, 0.5)

if calc_ticker and entry_p > stop_p:
    risk_per_share = entry_p - stop_p
    total_risk_allowed = (available_cash + (initial_value_dec_25)) * (risk_pct / 100)
    qty_to_buy = int(total_risk_allowed / risk_per_share)
    total_cost = qty_to_buy * entry_p
    
    # בדיקת חוק 3 הימים לפני/אחרי דוח
    try:
        s = yf.Ticker(calc_ticker)
        cal = s.calendar
        warning = ""
        if cal is not None and 'Earnings Date' in cal:
            e_date = cal['Earnings Date'][0].date()
            days_to_earnings = (e_date - datetime.date.today()).days
            if -3 <= days_to_earnings <= 3:
                warning = "⚠️ זהירות: דוח רווחים בטווח של 3 ימים!"
        
        st.sidebar.info(f"כמות לקנייה: {qty_to_buy} מניות")
        st.sidebar.write(f"עלות פוזיציה: ${total_cost:,.2f}")
        if warning: st.sidebar.warning(warning)
    except: pass

conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_trades = conn.read(ttl="0")
    if df_trades is not None and not df_trades.empty:
        df_trades.columns = df_trades.columns.str.strip()
        # ניקוי נתונים
        for col in ['Entry_Price', 'Qty', 'Exit_Price']:
            if col in df_trades.columns:
                df_trades[col] = pd.to_numeric(df_trades[col], errors='coerce').fillna(0)

        open_trades = df_trades[df_trades['Exit_Price'] == 0].copy()
        closed_trades = df_trades[df_trades['Exit_Price'] > 0].copy()

        # משיכה קבוצתית (מניעת שגיאות MSTR/ZETA/ONDS)
        open_tickers = [str(t).strip().upper() for t in open_trades['Ticker'].dropna().unique() if str(t).strip()]
        market_data = {}
        if open_tickers:
            data_download = yf.download(open_tickers, period="1y", group_by='ticker', progress=False)
            for t in open_tickers:
                try:
                    t_hist = data_download[t] if len(open_tickers) > 1 else data_download
                    if not t_hist.empty:
                        market_data[t] = {
                            'curr': t_hist['Close'].iloc[-1],
                            'ma150': t_hist['Close'].rolling(window=150).mean().iloc[-1],
                            'hist': t_hist
                        }
                except: continue

        # Sidebar Live
        market_value_stocks = 0
        total_unrealized_pnl = 0
        st.sidebar.divider()
        st.sidebar.subheader("פוזיציות פתוחות")
        for _, row in open_trades.iterrows():
            t = str(row['Ticker']).strip().upper()
            if t in market_data:
                curr = market_data[t]['curr']
                pos_val = curr * row['Qty']
                market_value_stocks += pos_val
                pnl = (curr - row['Entry_Price']) * row['Qty']
                total_unrealized_pnl += pnl
                st.sidebar.write(f"**{t}:** {pos_val:,.2f}$")
                st.sidebar.write(f":green[▲ +{pnl:,.2f}$]" if pnl >= 0 else f":red[▼ {pnl:,.2f}$]")

        # Unrealized P/L נקי
        st.sidebar.divider()
        st.sidebar.write("### Unrealized P/L")
        pnl_color = "green" if total_unrealized_pnl >= 0 else "red"
        st.sidebar.markdown(f"<h3 style='color:{pnl_color}; margin:0;'>${total_unrealized_pnl:,.2f}</h3>", unsafe_allow_html=True)

        # שווי כולל ודלתא
        total_val = market_value_stocks + available_cash
        diff = total_val - initial_value_dec_25
        st.sidebar.divider()
        st.sidebar.write("### שווי תיק כולל")
        st.sidebar.write(f"## ${total_val:,.2f}")
        
        d_color = "#ff4b4b" if diff < 0 else "#00c853"
        icon = "▼" if diff < 0 else "▲"
        label = "הפסד מתחילת השנה" if diff < 0 else "רווח מתחילת השנה"
        st.sidebar.markdown(f"""<div style="border: 1px solid {d_color}; border-radius: 5px; padding: 10px;">
            <p style="margin: 0; font-size: 14px; color: gray;">{label}</p>
            <h3 style="margin: 0; color: {d_color};">{icon} ${abs(diff):,.2f}</h3>
        </div>""", unsafe_allow_html=True)

        # תצוגה מרכזית
        tab1, tab2 = st.tabs(["🔓 טריידים פתוחים", "🔒 טריידים סגורים"])
        with tab1:
            st.dataframe(open_trades, use_container_width=True)
            st.subheader("🔍 תחקור טכני")
            for t in open_tickers:
                if t in market_data:
                    d = market_data[t]
                    with st.expander(f"ניתוח {t}"):
                        c1, c2 = st.columns([1, 2])
                        with c1:
                            if d['curr'] > d['ma150']: st.success("מעל 150 MA ✅")
                            else: st.error("מתחת ל-150 MA ❌")
                            st.write(f"מחיר: {d['curr']:.2f}$ | MA150: {d['ma150']:.2f}$")
                        with c2: st.line_chart(d['hist']['Close'].tail(60))

        with tab2:
            st.subheader("היסטוריית עסקאות")
            st.dataframe(closed_trades, use_container_width=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
