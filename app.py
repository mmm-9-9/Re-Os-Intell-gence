import os
import streamlit as st
from google import genai
import pandas as pd

# API anahtarÄ±nÄ± artÄ±k ortam deÄŸiÅŸkeninden okuyoruz.
# Render'da: Dashboard > Environment > Environment Variables > GEMINI_API_KEY ekle.
# Lokalde denemek iÃ§in: terminalde `export GEMINI_API_KEY="senin-anahtarin"` Ã§alÄ±ÅŸtÄ±r
# ya da aÅŸaÄŸÄ±daki satÄ±rÄ± geÃ§ici olarak aÃ§Ä±p anahtarÄ±nÄ± gir (deploy etmeden Ã¶nce SÄ°L).
API_KEY = os.environ.get("GEMINI_API_KEY")
# API_KEY = "buraya-lokal-test-icin-gecici-anahtar"

if not API_KEY:
    st.error("GEMINI_API_KEY ortam deÄŸiÅŸkeni bulunamadÄ±. Render > Environment kÄ±smÄ±ndan ekleyin.")
    st.stop()

client = genai.Client(api_key=API_KEY)
MODEL_NAME = "gemini-3.5-flash"  # gemini-1.5-flash artÄ±k kapatÄ±ldÄ±, yeni model bu

st.set_page_config(page_title="ReOs Intelligence", layout="wide")


def get_user_data():
    return pd.DataFrame({
        'Kod': ['Mertnine9', 'BASSGOD'],
        'MusteriAdi': ['Mert ÅanlÄ±', 'Che'],
        'PaketTuru': ['Admin', 'Pro']
    })


if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("ğŸ” ReOs GiriÅŸ")
    pw = st.text_input("Åifrenizi girin:", type="password")
    if st.button("GiriÅŸ Yap"):
        df = get_user_data()
        match = df[df['Kod'] == pw.strip()]
        if not match.empty:
            st.session_state.logged_in = True
            st.session_state.user = match.iloc[0]
            st.rerun()
        else:
            st.error("HatalÄ± ÅŸifre!")
else:
    with st.sidebar:
        st.header(f"ğŸ‘¤ {st.session_state.user['MusteriAdi']}")
        st.write(f"Paket: {st.session_state.user['PaketTuru']}")
        if st.button("Ã‡Ä±kÄ±ÅŸ Yap"):
            st.session_state.logged_in = False
            st.rerun()
        if st.session_state.user['Kod'] == 'Mertnine9':
            if st.checkbox("Admin Panelini GÃ¶ster"):
                st.dataframe(get_user_data())

    st.markdown("# RE-OS KÄ°ÅÄ°SEL ASÄ°STANINIZ")

    if 'messages' not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("ReOs'a bir ÅŸey yaz..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=f"Sen ReOs adÄ±nda uzman bir asistansÄ±n. Mert ve Che iÃ§in Ã§alÄ±ÅŸÄ±yorsun. KullanÄ±cÄ±: {prompt}"
                )
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"Hata: {e}")
