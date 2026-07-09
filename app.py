import streamlit as st
import pandas as pd

# 1. Google Sheets Linkin
URL = "https://docs.google.com/spreadsheets/d/1TSj4oPQn6NF4nxQ_0-wogDfAJTvnQo3Uz82Q4zfVnus/gviz/tq?tqx=out:csv"

st.set_page_config(page_title="RE-OS Intelligence", layout="wide")

@st.cache_data(ttl=10)
def load_data():
    df = pd.read_csv(URL)
    # Başlıklardaki olası boşlukları temizle
    df.columns = df.columns.str.strip()
    return df

st.title("RE-OS Intelligence v1.0")

try:
    df = load_data()
    
    # Giriş Ekranı
    code = st.text_input("Erişim Kodunu Gir:", type="password")
    
    if code:
        code = code.strip()
        # Kod sütununu stringe çevir ve boşlukları temizle
        match = df[df['Kod'].astype(str).str.strip() == code]
        
        if not match.empty:
            user_info = match.iloc[0]
            st.success(f"Hoş geldin, {user_info['MusteriAdi']}!")
            st.write(f"Paketin: {user_info['PaketTuru']}")
            
            # Admin Paneli İşlevleri
            if code == 'Mertnine9':
                st.divider()
                st.subheader("🛠 Admin Paneli")
                st.write("Sistem durumu: ✅ Online.")
                
                # Müşteri Listesini Göster
                st.subheader("📋 Tüm Müşteriler")
                st.dataframe(df, use_container_width=True)
                
                # Basit İstatistik
                st.metric("Toplam Müşteri Sayısı", len(df))
        else:
            st.error("Kod hatalı. Lütfen tekrar dene.")
            
except Exception as e:
    st.error(f"Sistem hatası: {e}. Lütfen Sheets paylaşım ayarlarını kontrol et.")

