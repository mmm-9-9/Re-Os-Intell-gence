import streamlit as st
import pandas as pd
import requests
from io import StringIO

st.set_page_config(page_title="RE-OS Intelligence", layout="wide")

# Google Sheets'ten veriyi çek
@st.cache_data(ttl=5)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1TSj4oPQn6NF4nxQ_0-wogDfAJTvnQo3Uz82Q4zfVnus/gviz/tq?tqx=out:csv"
    response = requests.get(url)
    if response.status_code == 200:
        df = pd.read_csv(StringIO(response.text))
        df.columns = df.columns.str.strip()
        return df
    return None

st.title("RE-OS Intelligence v1.0")

df = load_data()

if df is None:
    st.error("Sistem bağlantısı hatası.")
else:
    # Key Giriş Ekranı
    st.write("### Üyelik Erişimi")
    key_input = st.text_input("Lütfen size verilen Key'i girin:", type="password")
    
    if key_input:
        key_clean = key_input.strip()
        match = df[df['Kod'].astype(str).str.strip() == key_clean]
        
        if not match.empty:
            user_info = match.iloc[0]
            
            # --- ADMIN PANELİ (Sadece Mert) ---
            if key_clean == 'Mertnine9':
                st.divider()
                st.subheader("🛠 YÖNETİM MERKEZİ")
                st.dataframe(df, use_container_width=True)
                st.success("Admin girişi başarılı.")
            
            # --- MÜŞTERİ PANELİ (Key'i olanlar) ---
            else:
                st.success(f"Erişim sağlandı! Hoş geldin: {user_info['MusteriAdi']}")
                st.info(f"Üyelik Paketi: **{user_info['PaketTuru']}**")
                
                st.divider()
                st.write("### 🚀 RE-OS Hizmet Paneli")
                st.write("Üyeliğiniz aktif, hizmeti kullanmaya başlayabilirsiniz.")
                
                if st.button("Hizmeti Başlat"):
                    st.balloons()
                    st.success("Hizmetiniz başlatıldı ve sınırsız erişim tanımlandı!")
        else:
            st.error("Geçersiz Key! Lütfen kodunuzu kontrol edin.")

