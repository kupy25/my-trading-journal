import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
import datetime
import time

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 ניהול תיק והתפלגות נכסים - 2026")

# --- נתוני יסוד לפי TradeStation ---
initial_value_dec_25 = 44302.55
st.sidebar.header("⚙️ נתוני חשבון")
available_cash = st.sidebar.number_input("מזומן פנוי בחשבון ($)", value=5732.40, step=0.01)

# --- מחשבון גודל פוזיציה ---
st.sidebar.divider()
st.sidebar.subheader("🧮 מחשבון טרייד חדש")
calc_ticker = st.sidebar.text_input("טיקר לבדיקה", value="").strip().upper()
entry_p = st.sidebar.number_input("מחיר כניסה ($)", min_value=0.0, step=0.01)
stop_p = st.sidebar.number_input("סטופ לוס ($)", min_value=0.0, step=0.01)
risk_pct = st.sidebar.slider("סיכון מהתיק (%)", 0.25, 2.0, 1.0, 0.25)

if calc_ticker and entry_p > stop_p:
    money_at_risk = initial_value_dec_25 * (risk_pct / 100)
    risk_per_share = entry_p - stop_p
    qty_by_risk = int(money_at_risk / risk_per_share)
    qty_by_cash = int(available_cash / entry_p)
    final_qty = min(qty_by_risk, qty_by_cash)
    if final_qty > 0:
        st.sidebar.success(f"✅ כמות לקנייה: {final_qty} מניות")
        st.sidebar.write(f"💰 עלות: ${final_qty * entry_p:,.2f}")
    else: st.sidebar.error("אין מספיק מזומן פנוי!")

# חיבור לנתונים
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_trades = conn.read(ttl="0")
    if df_trades is not None and not df_trades.empty:
        df_trades.columns = df_trades.columns.str.strip()
        for col in ['Entry_Price', 'Qty', 'Exit_Price', 'PnL']:
            if col in df_trades.columns:
                df_trades[col] = pd.to_numeric(df_trades[col], errors='coerce').fillna(0)

        open_trades = df_trades[df_trades['Exit_Price'] == 0].copy()
        closed_trades = df_trades[df_trades['Exit_Price'] > 0].copy()

        # משיכה קבוצתית
        open_tickers = [str(t).strip().upper() for t in open_trades['Ticker'].dropna().unique()]
        market_data = {}
        if open_tickers:
            data_dl = yf.download(open_tickers, period="1y", group_by='ticker', progress=False)
            for t in open_tickers:
                try:
                    t_hist = data_dl[t] if len(open_tickers) > 1 else data_dl
                    if not t_hist.empty:
                        market_data[t] = {
                            'curr': t_hist['Close'].iloc[-1],
                            'ma150': t_hist['Close'].rolling(window=150).mean().iloc[-1],
                            'hist': t_hist
                        }
                except: continue

        # --- Sidebar: פוזיציות וצבעים ---
        market_value_stocks = 0
        total_unrealized_pnl = 0
        pie_data = [{"Asset": "Cash", "Value": available_cash}]
        
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
                pie_data.append({"Asset": t, "Value": pos_val})
                
                st.sidebar.write(f"**{t}:** {pos_val:,.2f}$")
                color = "#00c853" if pnl >= 0 else "#ff4b4b"
                st.sidebar.markdown(f"<p style='color:{color}; margin-top:-15px;'>{'+' if pnl >= 0 else ''}{pnl:,.2f}$</p>", unsafe_allow_html=True)

        # Unrealized P/L
        st.sidebar.divider()
        un_color = "#00c853" if total_unrealized_pnl >= 0 else "#ff4b4b"
        st.sidebar.write("### Unrealized P/L")
        st.sidebar.markdown(f"<h3 style='color:{un_color}; margin:0;'>${total_unrealized_pnl:,.2f}</h3>", unsafe_allow_html=True)

        # שווי כולל
        total_val = market_value_stocks + available_cash
        diff = total_val - initial_value_dec_25
        st.sidebar.divider()
        st.sidebar.write("### שווי תיק כולל")
        st.sidebar.write(f"## ${total_val:,.2f}")
        
        d_color = "#ff4b4b" if diff < 0 else "#00c853"
        icon, label = ("▼", "הפסד מתחילת השנה") if diff < 0 else ("▲", "רווח מתחילת השנה")
        st.sidebar.markdown(f"<div style='border: 1px solid {d_color}; padding: 10px; border-radius: 5px;'><p style='margin:0; color:gray;'>{label}</p><h3 style='margin:0; color:{d_color};'>{icon} ${abs(diff):,.2f}</h3></div>", unsafe_allow_html=True)

        # --- הוספת גרף עוגה עם לייבלים ---
        st.sidebar.divider()
        st.sidebar.subheader("📊 התפלגות הון")
        fig_pie = px.pie(
            pd.DataFrame(pie_data), 
            values='Value', 
            names='Asset', 
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        # עדכון הלייבלים שיופיעו על הגרף
        fig_pie.update_traces(textinfo='label+percent', textposition='inside')
        fig_pie.update_layout(margin=dict(l=0, r=0, t=10, b=10), showlegend=False)
        st.sidebar.plotly_chart(fig_pie, use_container_width=True)

        # --- תצוגה מרכזית ---
        tab1, tab2 = st.tabs(["🔓 טריידים פתוחים", "🔒 טריידים סגורים"])
        with tab1:
            st.subheader("פוזיציות פעילות")
            st.dataframe(open_trades, use_container_width=True)
            st.subheader("🔍 תחקור טכני 150 MA")
            for t in open_tickers:
                if t in market_data:
                    d = market_data[t]
                    with st.expander(f"ניתוח {t}"):
                        c1, c2 = st.columns([1, 2])
                        with c1:
                            st.write(f"מחיר: {d['curr']:.2f}$ | MA150: {d['ma150']:.2f}$")
                            if d['curr'] > d['ma150']: st.success("מעל 150 MA ✅")
                            else: st.error("מתחת ל-150 MA ❌")
                        with c2: st.line_chart(d['hist']['Close'].tail(60))

        with tab2:
            st.subheader("היסטוריית עסקאות")
            st.dataframe(closed_trades, use_container_width=True)

except Exception as e:
    st.error(f"שגיאה: {e}")
