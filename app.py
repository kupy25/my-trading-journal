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

# --- מחשבון גודל פוזיציה מתוקן ---
st.sidebar.divider()
st.sidebar.subheader("🧮 מחשבון טרייד חדש")
calc_ticker = st.sidebar.text_input("טיקר לבדיקה (למשל TSLA)", value="").strip().upper()
entry_p = st.sidebar.number_input("מחיר כניסה מתוכנן ($)", min_value=0.0, value=0.0, step=0.1)
stop_p = st.sidebar.number_input("סטופ לוס מתוכנן ($)", min_value=0.0, value=0.0, step=0.1)
risk_pct = st.sidebar.slider("סיכון מהתיק (%)", 0.5, 3.0, 1.0, 0.5)

# הצגת תוצאות המחשבון
if calc_ticker and entry_p > 0 and stop_p > 0:
    if entry_p <= stop_p:
        st.sidebar.error("הסטופ חייב להיות נמוך ממחיר הכניסה!")
    else:
        risk_per_share = entry_p - stop_p
        # חישוב סיכון לפי שווי התיק המעודכן (מזומן + שווי התחלתי כבסיס)
        total_portfolio_est = initial_value_dec_25 
        money_to_risk = total_portfolio_est * (risk_pct / 100)
        
        qty_to_buy = int(money_to_risk / risk_per_share)
        total_cost = qty_to_buy * entry_p
        
        st.sidebar.success(f"✅ כמות לקנייה: {qty_to_buy} מניות")
        st.sidebar.write(f"💰 עלות כוללת: ${total_cost:,.2f}")
        st.sidebar.write(f"📉 סיכון כספי בטרייד: ${money_to_risk:,.2f}")

        # בדיקת חוק 3 הימים (Earnings)
        try:
            with st.spinner('בודק תאריך דוח...'):
                s = yf.Ticker(calc_ticker)
                cal = s.calendar
                if cal is not None and 'Earnings Date' in cal:
                    e_date = cal['Earnings Date'][0].date()
                    days_diff = (e_date - datetime.date.today()).days
                    st.sidebar.write(f"📅 דוח קרוב ב: {e_date}")
                    if -3 <= days_diff <= 3:
                        st.sidebar.warning("⚠️ זהירות! דוח בטווח של 3 ימים!")
                    else:
                        st.sidebar.info("✅ אין דוח קרוב (תקין לפי הכללים)")
        except:
            st.sidebar.write("⚠️ לא ניתן היה למשוך תאריך דוח.")

# --- המשך הקוד (ניהול התיק) ---
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_trades = conn.read(ttl="0")
    if df_trades is not None and not df_trades.empty:
        df_trades.columns = df_trades.columns.str.strip()
        for col in ['Entry_Price', 'Qty', 'Exit_Price']:
            if col in df_trades.columns:
                df_trades[col] = pd.to_numeric(df_trades[col], errors='coerce').fillna(0)

        open_trades = df_trades[df_trades['Exit_Price'] == 0].copy()
        
        # משיכה קבוצתית למניעת שגיאות טעינה
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

        # Sidebar - פוזיציות ו-P/L
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
                st.sidebar.write(f"**{t}:** {pos_val:,.2f}$ | :{'green' if pnl >= 0 else 'red'}[{pnl:,.2f}$]")

        # Unrealized P/L
        st.sidebar.divider()
        st.sidebar.write("### Unrealized P/L")
        st.sidebar.markdown(f"<h3 style='color:{'#00c853' if total_unrealized_pnl >= 0 else '#ff4b4b'}; margin:0;'>${total_unrealized_pnl:,.2f}</h3>", unsafe_allow_html=True)

        # שווי כולל
        total_val = market_value_stocks + available_cash
        diff = total_val - initial_value_dec_25
        st.sidebar.divider()
        st.sidebar.write("### שווי תיק כולל")
        st.sidebar.write(f"## ${total_val:,.2f}")
        
        color = "#ff4b4b" if diff < 0 else "#00c853"
        icon, label = ("▼", "הפסד מתחילת השנה") if diff < 0 else ("▲", "רווח מתחילת השנה")
        st.sidebar.markdown(f"<div style='border: 1px solid {color}; padding: 10px; border-radius: 5px;'><p style='margin:0; color:gray;'>{label}</p><h3 style='margin:0; color:{color};'>{icon} ${abs(diff):,.2f}</h3></div>", unsafe_allow_html=True)

        # טבלאות מרכזיות
        tab1, tab2 = st.tabs(["🔓 טריידים פתוחים", "🔒 טריידים סגורים"])
        with tab1:
            st.dataframe(open_trades, use_container_width=True)
            st.subheader("🔍 תחקור טכני 150 MA")
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
            st.dataframe(df_trades[df_trades['Exit_Price'] > 0], use_container_width=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
