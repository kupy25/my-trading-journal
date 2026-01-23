import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_gsheets import GSheetsConnection

# הגדרות דף
st.set_page_config(page_title="יומן המסחר של אבי", layout="wide")
st.title("📊 יומן מסחר ותחקור - 2026")

# חיבור ל-Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # טעינת נתונים - ttl="0" מבטיח רענון מיידי בכל פעם
    df_trades = conn.read(ttl="0")
    
    if df_trades is not None and not df_trades.empty:
        # ניקוי שמות עמודות מרווחים מיותרים
        df_trades.columns = df_trades.columns.str.strip()

        # חישוב רווח כולל בבטחה
        if 'PnL' in df_trades.columns:
            total_pnl = pd.to_numeric(df_trades['PnL'], errors='coerce').sum()
            st.sidebar.metric("רווח/הפסד כולל (YTD)", f"${total_pnl:,.2f}")
        
        st.subheader("יומן הטריידים שלך")
        
        # חישוב עלות כוללת לתצוגה
        if 'Entry_Price' in df_trades.columns and 'Qty' in df_trades.columns:
            df_trades['Entry_Price'] = pd.to_numeric(df_trades['Entry_Price'], errors='coerce')
            df_trades['Qty'] = pd.to_numeric(df_trades['Qty'], errors='coerce')
            df_trades['Total_Cost'] = df_trades['Entry_Price'] * df_trades['Qty']

        st.dataframe(df_trades, use_container_width=True)

        # תחקור אוטומטי
        st.subheader("🔍 תחקור ביצועים וכללי ברזל (Live)")
        if 'Ticker' in df_trades.columns:
            for ticker in df_trades['Ticker'].unique():
                if pd.isna(ticker): continue
                with st.expander(f"ניתוח טכני עבור {ticker}"):
                    try:
                        stock = yf.Ticker(str(ticker))
                        hist = stock.history(period="1y")
                        if not hist.empty:
                            curr = hist['Close'].iloc[-1]
                            ma150 = hist['Close'].rolling(window=150).mean().iloc[-1]
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if curr > ma150:
                                    st.success(f"✅ מעל 150 MA (מחיר: {curr:.2f}, ממוצע: {ma150:.2f})")
                                else:
                                    st.error(f"❌ מתחת ל-150 MA (מחיר: {curr:.2f}, ממוצע: {ma150:.2f})")
                            with col2:
                                # הצגת גרף קטן של המניה
                                st.line_chart(hist['Close'].tail(50))
                    except Exception as e:
                        st.write(f"לא ניתן לנתח את {ticker}")
    else:
        st.info("הגיליון ריק או לא נגיש. וודא שהזנת נתונים ב-Google Sheets.")

except Exception as e:
    st.error(f"שגיאה בטעינת הנתונים: {e}")
    st.info("טיפ: וודא ששמות העמודות בגיליון תואמים בדיוק למה שהגדרנו.")
