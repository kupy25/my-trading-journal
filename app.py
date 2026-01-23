import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 יומן מסחר ותחקור - 2026")

# חיבור ל-Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# טעינת נתונים
df_trades = conn.read(ttl="1m")

# --- מנגנון הזנה אוטומטית לטריידים מתחילת השנה ---
if df_trades.empty or len(df_trades) < 2:
    st.info("מבצע הזנה ראשונית של טריידים מתחילת השנה...")
    initial_data = pd.DataFrame([
        {"Ticker": "SEDG", "Entry_Date": "2026-01-05", "Entry_Price": 32.92, "Qty": 174, "Exit_Price": 30.45, "PnL": -430.87, "Reason": "תחקיר", "Notes": "מתחת ל-150 MA"},
        {"Ticker": "PONY", "Entry_Date": "2026-01-06", "Entry_Price": 17.35, "Qty": 144, "Exit_Price": 15.47, "PnL": -270.69, "Reason": "תחקיר", "Notes": ""},
        {"Ticker": "RIVN", "Entry_Date": "2026-01-06", "Entry_Price": 19.20, "Qty": 286, "Exit_Price": 17.40, "PnL": -515.56, "Reason": "תחקיר", "Notes": "סקטור חלש"},
        {"Ticker": "RDDT", "Entry_Date": "2025-09-20", "Entry_Price": 259.60, "Qty": 20, "Exit_Price": 218.64, "PnL": -819.18, "Reason": "החזקה ארוכה", "Notes": ""},
        {"Ticker": "PLTR", "Entry_Date": "2025-11-25", "Entry_Price": 164.60, "Qty": 34, "Exit_Price": 166.42, "PnL": 61.97, "Reason": "מימוש רווח", "Notes": ""},
        {"Ticker": "APA", "Entry_Date": "2026-01-20", "Entry_Price": 25.87, "Qty": 208, "Exit_Price": 26.15, "PnL": 58.28, "Reason": "מימוש מהיר", "Notes": "מעל 150 MA"}
    ])
    conn.update(data=initial_data)
    st.success("הנתונים הוזנו בהצלחה לגיליון גוגל!")
    st.rerun()

# --- המשך האתר הרגיל ---
st.sidebar.metric("רווח/הפסד כולל (YTD)", f"${df_trades['PnL'].sum():,.2f}")

# הצגת הטבלה
st.subheader("יומן הטריידים שלך (מסונכרן עם Google Sheets)")
display_df = df_trades.copy()
display_df['Total_Cost'] = display_df['Entry_Price'] * display_df['Qty']
st.dataframe(display_df, use_container_width=True)

# תחקור אוטומטי
st.subheader("🔍 תחקור ביצועים וכללי ברזל")
for index, row in df_trades.iterrows():
    ticker = row['Ticker']
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        curr = hist['Close'].iloc[-1]
        ma150 = hist['Close'].rolling(window=150).mean().iloc[-1]
        
        status = "✅ מעל 150 MA" if curr > ma150 else "❌ מתחת ל-150 MA"
        st.write(f"**{ticker}**: {status} | מחיר כניסה: {row['Entry_Price']}$ | מחיר נוכחי: {curr:.2f}$")
    except:
        continue
