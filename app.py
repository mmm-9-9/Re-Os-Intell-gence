import streamlit as st
import pandas as pd


URL = https://docs.google.com/spreadsheets/d/18O2AD3vtLwW8VIld8xKy04ANKIar0qvPMY_AEA23-4U/edit?usp=sharing

@st.cache_data(ttl=10)
def load_data():
    return pd.read_csv(URL)

st.title("RE-OS Intelligence v1.0")

try:
    df = load_data()
    code = st.text_input("Erişim Kodunu Gir:")

    if code:
        code = code.strip()
        match = df[df['Kod'] == code]
        
        if not match.empty:
            user_info = match.iloc[0]
            st.success(f"Hoş geldin, {user_info['MusteriAdi']}!")
            st.write(f"Paketin: {user_info['PaketTuru']}")
            
            if code == 'Mertnine9':
                st.divider()
                st.subheader("Admin Paneli")
                st.write("Sistem durumu: ✅ Online.")
        else:
            st.error("Kod hatalı. Lütfen tekrar dene.")
except Exception as e:
    st.error("Google Sheets'e bağlanılamadı. Paylaşım ayarlarını kontrol et.")

