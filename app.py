import os
import streamlit as st
import anthropic
import pandas as pd

# API anahtarÄ±nÄ± ortam deÄŸiÅŸkeninden okuyoruz.
# Render'da: Dashboard > Environment > Environment Variables > ANTHROPIC_API_KEY ekle.
# AnahtarÄ± buradan alabilirsin: https://console.anthropic.com/settings/keys
# GerÃ§ek anahtar "sk-ant-..." ile baÅŸlar.
API_KEY = os.environ.get("ANTHROPIC_API_KEY")

if not API_KEY:
    st.error("ANTHROPIC_API_KEY ortam deÄŸiÅŸkeni bulunamadÄ±. Render > Environment kÄ±smÄ±ndan ekleyin.")
    st.stop()

client = anthropic.Anthropic(api_key=API_KEY)
MODEL_NAME = "claude-sonnet-5"  # ihtiyaca gÃ¶re "claude-haiku-4-5-20251001" (daha ucuz/hÄ±zlÄ±) da kullanÄ±labilir

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
                # Ã–nceki mesajlarÄ± da API'ye gÃ¶nderiyoruz ki asistan konuÅŸma geÃ§miÅŸini hatÄ±rlasÄ±n
                api_messages = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ]
                response = client.messages.create(
                    model=MODEL_NAME,
                    max_tokens=1024,
                    system=(
                        "Sen ReOs adÄ±nda uzman bir kiÅŸisel asistansÄ±n. "
                        "Mert ve Che iÃ§in Ã§alÄ±ÅŸÄ±yorsun. Birden fazla konuda "
                        "(iÅŸ takibi, planlama, genel danÄ±ÅŸmanlÄ±k vb.) yardÄ±mcÄ± olabilirsin. "
                        "Net, kÄ±sa ve faydalÄ± cevaplar ver."
                    ),
                    messages=api_messages,
                )
                answer = response.content[0].text
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error(f"Hata: {e}")
