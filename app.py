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
try:
    df_trades = conn.read(ttl="1m")
    
    if not df_trades.empty:
        # סיכום בתפריט צד
        total_pnl = df_trades['PnL'].sum()
        st.sidebar.metric("רווח/הפסד כולל (YTD)", f"${total_pnl:,.2f}")

        # הצגת הטבלה
        st.subheader("יומן הטריידים שלך")
        display_df = df_trades.copy()
        display_df['Total_Cost'] = display_df['Entry_Price'] * display_df['Qty']
        st.dataframe(display_df, use_container_width=True)

        # תחקור אוטומטי
        st.subheader("🔍 תחקור ביצועים וכללי ברזל (Live)")
        for index, row in df_trades.iterrows():
            ticker = row['Ticker']
            with st.expander(f"ניתוח עבור {ticker}"):
                try:
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period="1y")
                    curr = hist['Close'].iloc[-1]
                    ma150 = hist['Close'].rolling(window=150).mean().iloc[-1]
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if curr > ma150:
                            st.success(f"✅ מעל 150 MA (מחיר: {curr:.2f}, ממוצע: {ma150:.2f})")
                        else:
                            st.error(f"❌ מתחת ל-150 MA (מחיר: {curr:.2f}, ממוצע: {ma150:.2f})")
                    with col2:
                        st.write(f"**סיבת כניסה:** {row['Reason']}")
                        st.write(f"**הערות:** {row['Notes']}")
                except:
                    st.warning(f"לא ניתן למשוך נתונים עבור {ticker}")
    else:
        st.info("הגיליון ריק. הזן נתונים ב-Google Sheets כדי לראות אותם כאן.")
except Exception as e:
    st.error(f"שגיאה בחיבור לגיליון: {e}")
