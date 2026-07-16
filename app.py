import streamlit as st
import google.generativeai as genai
import pandas as pd
import os

# API anahtarını doğrudan environment değişkeni olarak tanımlıyoruz ki kütüphane kaçamasın
os.environ["GOOGLE_API_KEY"] = "AQ.Ab8RN6KXU8FJ1vMqjS_se8G0-zoUmUrxzKsX6P4w1slrbVP0gw"
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

# Modeli güncelliyoruz
model = genai.GenerativeModel("gemini-1.5-flash")

st.set_page_config(page_title="ReOs Intelligence", layout="wide")

def get_user_data():
    return pd.DataFrame({
        'Kod': ['Mertnine9', 'BASSGOD'],
        'MusteriAdi': ['Mert Şanlı', 'Che'],
        'PaketTuru': ['Admin', 'Pro']
    })

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 ReOs Giriş")
    pw = st.text_input("Şifrenizi girin:", type="password")
    if st.button("Giriş Yap"):
        df = get_user_data()
        match = df[df['Kod'] == pw.strip()]
        if not match.empty:
            st.session_state.logged_in = True
            st.session_state.user = match.iloc[0]
            st.rerun()
        else:
            st.error("Hatalı şifre!")
else:
    with st.sidebar:
        st.header(f"👤 {st.session_state.user['MusteriAdi']}")
        st.write(f"Paket: {st.session_state.user['PaketTuru']}")
        if st.button("Çıkış Yap"):
            st.session_state.logged_in = False
            st.rerun()
        if st.session_state.user['Kod'] == 'Mertnine9':
            if st.checkbox("Admin Panelini Göster"):
                st.dataframe(get_user_data())

    st.markdown("# RE-OS KİŞİSEL ASİSTANINIZ")
    
    if 'messages' not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("ReOs'a bir şey yaz..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        with st.chat_message("assistant"):
            try:
                # Modeli çağırırken daha spesifik bir talimat veriyoruz
                full_prompt = f"Sen ReOs adında uzman bir asistansın. Mert ve Che için çalışıyorsun. Profesyonel, yardımsever ve çözüm odaklısın. Kullanıcı: {prompt}"
                response = model.generate_content(full_prompt)
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"ReOs şu an teknik bir aksaklık yaşıyor: {e}")

