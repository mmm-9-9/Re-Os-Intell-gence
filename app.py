import os
import streamlit as st
from google import genai
import pandas as pd

# API anahtarını ortam değişkeninden okuyoruz.
# Render'da: Dashboard > Environment > Environment Variables > GEMINI_API_KEY ekle.
# Anahtarı buradan al: https://aistudio.google.com/apikey
# Not: Google artık "AQ.Ab..." formatında anahtar veriyor, bu normal ve geçerli.
API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    st.error("GEMINI_API_KEY ortam değişkeni bulunamadı. Render > Environment kısmından ekleyin.")
    st.stop()

client = genai.Client(api_key=API_KEY)
MODEL_NAME = "gemini-3.5-flash"  # ücretsiz katmanda günlük 1500 istek, dakikada 15 istek

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
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=f"Sen ReOs adında uzman bir asistansın. Mert ve Che için çalışıyorsun. Kullanıcı: {prompt}"
                )
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"Hata: {e}")
