import os
import sqlite3
import datetime
import requests
import streamlit as st
from google import genai
from google.genai import types
import pandas as pd

# ============ AYARLAR ============
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    st.error("GEMINI_API_KEY ortam değişkeni bulunamadı. Render > Environment kısmından ekleyin.")
    st.stop()

client = genai.Client(api_key=API_KEY)
MODEL_NAME = "gemini-3.5-flash"
DB_PATH = "reos_data.db"

st.set_page_config(page_title="ReOs Intelligence", layout="wide")


# ============ VERİTABANI ============
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_kod TEXT NOT NULL,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        ts TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS user_settings (
        user_kod TEXT PRIMARY KEY,
        custom_instructions TEXT
    )""")
    conn.commit()
    return conn


def create_conversation(user_kod, title):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO conversations (user_kod, title, created_at) VALUES (?, ?, ?)",
        (user_kod, title, datetime.datetime.now().isoformat())
    )
    conn.commit()
    conv_id = cur.lastrowid
    conn.close()
    return conv_id


def get_conversations(user_kod):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, title FROM conversations WHERE user_kod = ? ORDER BY id DESC",
        (user_kod,)
    ).fetchall()
    conn.close()
    return rows


def rename_conversation(conv_id, title):
    conn = get_conn()
    conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conv_id))
    conn.commit()
    conn.close()


def add_message(conv_id, role, content):
    conn = get_conn()
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, ts) VALUES (?, ?, ?, ?)",
        (conv_id, role, content, datetime.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_messages(conv_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id ASC",
        (conv_id,)
    ).fetchall()
    conn.close()
    return [{"role": r, "content": c} for r, c in rows]


def get_custom_instructions(user_kod):
    conn = get_conn()
    row = conn.execute(
        "SELECT custom_instructions FROM user_settings WHERE user_kod = ?", (user_kod,)
    ).fetchone()
    conn.close()
    return row[0] if row else ""


def set_custom_instructions(user_kod, text):
    conn = get_conn()
    conn.execute(
        "INSERT INTO user_settings (user_kod, custom_instructions) VALUES (?, ?) "
        "ON CONFLICT(user_kod) DO UPDATE SET custom_instructions = excluded.custom_instructions",
        (user_kod, text)
    )
    conn.commit()
    conn.close()


# ============ YARDIMCI FONKSİYONLAR ============
def get_bursa_weather():
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": 40.1826,
                "longitude": 29.0669,
                "current": "temperature_2m,weather_code",
                "timezone": "auto",
            },
            timeout=5,
        )
        data = r.json()
        temp = data["current"]["temperature_2m"]
        return f"Bursa'da şu an hava yaklaşık {temp}°C."
    except Exception:
        return "Hava durumu bilgisi şu an alınamadı."


def build_system_prompt(custom_instructions):
    now = datetime.datetime.now()
    gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    tarih_str = f"{now.day} {['Ocak','Şubat','Mart','Nisan','Mayıs','Haziran','Temmuz','Ağustos','Eylül','Ekim','Kasım','Aralık'][now.month-1]} {now.year}, {gunler[now.weekday()]}"
    hava = get_bursa_weather()

    prompt = (
        "Sen ReOs adında, kullanıcıya yardımcı olan uzman bir kişisel asistansın. "
        "Net, kısa ve faydalı cevaplar ver.\n\n"
        f"Bugünün tarihi: {tarih_str}.\n"
        f"Güncel hava durumu: {hava}\n"
    )
    if custom_instructions and custom_instructions.strip():
        prompt += f"\nKullanıcının senin için verdiği özel talimatlar:\n{custom_instructions.strip()}\n"
    return prompt


def build_gemini_contents(messages):
    contents = []
    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))
    return contents


def get_user_data():
    return pd.DataFrame({
        'Kod': ['Mertnine9', 'BASSGOD'],
        'MusteriAdi': ['Mert Şanlı', 'Che'],
        'PaketTuru': ['Admin', 'Pro']
    })


# ============ GİRİŞ ============
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
            st.session_state.active_conv_id = None
            st.rerun()
        else:
            st.error("Hatalı şifre!")

else:
    user_kod = st.session_state.user['Kod']
    user_name = st.session_state.user['MusteriAdi']
    package = st.session_state.user['PaketTuru']

    # Aktif sohbet yoksa, en son sohbeti yükle ya da yeni oluştur
    if st.session_state.get('active_conv_id') is None:
        existing = get_conversations(user_kod)
        if existing:
            st.session_state.active_conv_id = existing[0][0]
        else:
            st.session_state.active_conv_id = create_conversation(user_kod, "Yeni Sohbet")

    with st.sidebar:
        st.header(f"👤 {user_name}")
        st.write(f"Paket: {package}")
        if st.button("Çıkış Yap"):
            st.session_state.logged_in = False
            st.session_state.active_conv_id = None
            st.rerun()

        st.divider()
        if st.button("➕ Yeni Sohbet"):
            st.session_state.active_conv_id = create_conversation(user_kod, "Yeni Sohbet")
            st.rerun()

        st.subheader("🕘 Geçmiş Sohbetler")
        for conv_id, title in get_conversations(user_kod):
            label = title if conv_id != st.session_state.active_conv_id else f"➡️ {title}"
            if st.button(label, key=f"conv_{conv_id}"):
                st.session_state.active_conv_id = conv_id
                st.rerun()

        if package == "Pro":
            st.divider()
            st.subheader("⚙️ Özelleştirme")
            current_instr = get_custom_instructions(user_kod)
            new_instr = st.text_area(
                "Asistan senin için nasıl davransın?",
                value=current_instr,
                height=150,
                key="custom_instr_box",
            )
            if st.button("Kaydet", key="save_instr"):
                set_custom_instructions(user_kod, new_instr)
                st.success("Kaydedildi.")

        if user_kod == 'Mertnine9':
            st.divider()
            if st.checkbox("Admin Panelini Göster"):
                st.dataframe(get_user_data())

    st.markdown("# RE-OS KİŞİSEL ASİSTANINIZ")

    active_conv_id = st.session_state.active_conv_id
    messages = get_messages(active_conv_id)

    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("ReOs'a bir şey yaz..."):
        is_first_message = len(messages) == 0

        add_message(active_conv_id, "user", prompt)
        with st.chat_message("user"):
            st.markdown(prompt)

        if is_first_message:
            title_guess = prompt.strip()[:40] + ("..." if len(prompt.strip()) > 40 else "")
            rename_conversation(active_conv_id, title_guess)

        with st.chat_message("assistant"):
            try:
                custom_instructions = get_custom_instructions(user_kod) if package == "Pro" else ""
                system_prompt = build_system_prompt(custom_instructions)
                all_messages = get_messages(active_conv_id)
                contents = build_gemini_contents(all_messages)

                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=contents,
                    config=types.GenerateContentConfig(system_instruction=system_prompt),
                )
                answer = response.text
                st.markdown(answer)
                add_message(active_conv_id, "assistant", answer)
            except Exception as e:
                st.error(f"Hata: {e}")
