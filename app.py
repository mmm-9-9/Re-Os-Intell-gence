import streamlit as st
import pandas as pd

# Sayfa ayarları
st.set_page_config(page_title="ReOs", layout="wide")

# Veri yapısı
def get_user_data():
    data = {
        'Kod': ['Mertnine9', 'BASSGOD'],
        'MusteriAdi': ['Mert Şanlı', 'Che'],
        'PaketTuru': ['Admin', 'Pro']
    }
    return pd.DataFrame(data)

# Oturum yönetimi
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

def login():
    st.title("🔐 Giriş Ekranı")
    pw = st.text_input("Şifrenizi girin:", type="password")
    if st.button("Giriş Yap"):
        df = get_user_data()
        match = df[df['Kod'].astype(str).str.strip() == pw.strip()]
        if not match.empty:
            st.session_state.logged_in = True
            st.session_state.user = match.iloc[0]
            st.rerun()
        else:
            st.error("Hatalı şifre!")

# Ana Arayüz
if not st.session_state.logged_in:
    login()
else:
    # Yan Menü (Sidebar)
    with st.sidebar:
        st.header(f"👤 {st.session_state.user['MusteriAdi']}")
        st.write(f"Paket: {st.session_state.user['PaketTuru']}")
        st.divider()
        if st.button("Çıkış Yap"):
            st.session_state.logged_in = False
            st.rerun()
        
        # Admin Paneli erişimi
        if st.session_state.user['Kod'] == 'Mertnine9':
            st.divider()
            if st.checkbox("Admin Panelini Göster"):
                st.dataframe(get_user_data())

    # Ana Ekran
    st.markdown("# RE-OS KİŞİSEL ASİSTANINIZ")
    st.write(f"Hoş geldin, {st.session_state.user['MusteriAdi']}. ReOs hazır, seni dinliyorum.")
    
    # Sohbet (Chat) Arayüzü
    if 'messages' not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("ReOs'a bir şey yaz..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        # ReOs Cevabı
        response = f"ReOs olarak mesajını aldım: '{prompt}'. Sınırsız hizmet modunda işliyorum."
        st.session_state.messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)

