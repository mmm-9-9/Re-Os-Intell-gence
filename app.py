import streamlit as st
import pandas as pd

st.set_page_config(page_title="ReOs Intelligence", layout="wide")

# ReOs Sistem Veritabanı
def get_user_data():
    data = {
        'Kod': ['Mertnine9', 'BASSGOD'],
        'MusteriAdi': ['Mert Şanlı', 'Che'],
        'PaketTuru': ['Admin', 'Pro']
    }
    return pd.DataFrame(data)

st.title("🤖 ReOs Intelligence")
st.subheader("Sınırsız Hizmet Platformu")

df = get_user_data()
key_input = st.text_input("Lütfen size verilen Key'i girin:", type="password")

if key_input:
    key_clean = key_input.strip()
    match = df[df['Kod'].astype(str).str.strip() == key_clean]
    
    if not match.empty:
        user_info = match.iloc[0]
        st.success(f"Merhaba, ben **ReOs**. Hoş geldin, {user_info['MusteriAdi']}.")
        st.info(f"Aktif Paket: **{user_info['PaketTuru']}**")
        
        # Admin ve Pro için özel yetkiler
        if key_clean == 'Mertnine9':
            st.divider()
            st.subheader("🛠 ReOs Yönetim Paneli")
            st.dataframe(df, use_container_width=True)
        
        # Hizmet Başlatma
        if st.button("ReOs Hizmetini Başlat"):
            st.balloons()
            st.write("✅ **ReOs:** Hizmetiniz başlatıldı ve sınırsız erişim tanımlandı. Hazırım, ne yapmamı istersin?")
    else:
        st.error("❌ Geçersiz Key!")

