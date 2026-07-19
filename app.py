import os
import re
import sqlite3
import secrets
import hashlib
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

# Bu email ile kayıt olan kişi otomatik Admin olur. Render'da ADMIN_EMAIL
# ortam değişkeni olarak kendi mailini ekle.
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower()

st.set_page_config(page_title="ReOs Intelligence", layout="wide")


# ============ VERİTABANI ============
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        ad_soyad TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        paket TEXT NOT NULL DEFAULT 'Ücretsiz',
        is_admin INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
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
        user_id INTEGER PRIMARY KEY,
        custom_instructions TEXT
    )""")
    conn.commit()
    return conn


# ============ ŞİFRE GÜVENLİĞİ ============
def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100_000).hex()
    return pwd_hash, salt


def verify_password(password, salt, stored_hash):
    check_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(check_hash, stored_hash)


# ============ KULLANICI İŞLEMLERİ ============
def email_valid(email):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None


def get_user_by_email(email):
    conn = get_conn()
    row = conn.execute(
        "SELECT id, email, ad_soyad, password_hash, salt, paket, is_admin FROM users WHERE email = ?",
        (email.strip().lower(),)
    ).fetchone()
    conn.close()
    return row


def create_user(email, ad_soyad, password):
    email = email.strip().lower()
    pwd_hash, salt = hash_password(password)
    is_admin = 1 if (ADMIN_EMAIL and email == ADMIN_EMAIL) else 0
    paket = "Admin" if is_admin else "Ücretsiz"
    conn = get_conn()
    conn.execute(
        "INSERT INTO users (email, ad_soyad, password_hash, salt, paket, is_admin, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (email, ad_soyad, pwd_hash, salt, paket, is_admin, datetime.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_all_users():
    conn = get_conn()
    rows = conn.execute("SELECT id, email, ad_soyad, paket, created_at FROM users ORDER BY id").fetchall()
    conn.close()
    return rows


def update_user_package(user_id, paket):
    conn = get_conn()
    conn.execute("UPDATE users SET paket = ? WHERE id = ?", (paket, user_id))
    conn.commit()
    conn.close()


# ============ SOHBET VERİTABANI ============
def create_conversation(user_id, title):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO conversations (user_id, title, created_at) VALUES (?, ?, ?)",
        (user_id, title, datetime.datetime.now().isoformat())
    )
    conn.commit()
    conv_id = cur.lastrowid
    conn.close()
    return conv_id


def get_conversations(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, title FROM conversations WHERE user_id = ? ORDER BY id DESC",
        (user_id,)
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


def get_custom_instructions(user_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT custom_instructions FROM user_settings WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row[0] if row and row[0] else ""


def set_custom_instructions(user_id, text):
    conn = get_conn()
    conn.execute(
        "INSERT INTO user_settings (user_id, custom_instructions) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET custom_instructions = excluded.custom_instructions",
        (user_id, text)
    )
    conn.commit()
    conn.close()


# ============ ASİSTAN YARDIMCILARI ============
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
    aylar = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
             "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    tarih_str = f"{now.day} {aylar[now.month-1]} {now.year}, {gunler[now.weekday()]}"
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


# ============ GİRİŞ / KAYIT ============
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 ReOs")
    tab_giris, tab_kayit = st.tabs(["Giriş Yap", "Kayıt Ol"])

    with tab_giris:
        email = st.text_input("Email", key="login_email")
        pw = st.text_input("Şifre", type="password", key="login_pw")
        if st.button("Giriş Yap"):
            user = get_user_by_email(email)
            if user and verify_password(pw, user[4], user[3]):
                st.session_state.logged_in = True
                st.session_state.user = {
                    "id": user[0], "email": user[1], "ad_soyad": user[2],
                    "paket": user[5], "is_admin": bool(user[6]),
                }
                st.session_state.active_conv_id = None
                st.rerun()
            else:
                st.error("Email veya şifre hatalı.")

    with tab_kayit:
        yeni_ad = st.text_input("Ad Soyad", key="reg_ad")
        yeni_email = st.text_input("Email", key="reg_email")
        yeni_pw = st.text_input("Şifre", type="password", key="reg_pw")
        yeni_pw2 = st.text_input("Şifre (tekrar)", type="password", key="reg_pw2")
        if st.button("Kayıt Ol"):
            if not yeni_ad.strip():
                st.error("Ad soyad giriniz.")
            elif not email_valid(yeni_email):
                st.error("Geçerli bir email giriniz.")
            elif len(yeni_pw) < 6:
                st.error("Şifre en az 6 karakter olmalı.")
            elif yeni_pw != yeni_pw2:
                st.error("Şifreler eşleşmiyor.")
            elif get_user_by_email(yeni_email):
                st.error("Bu email zaten kayıtlı.")
            else:
                create_user(yeni_email, yeni_ad.strip(), yeni_pw)
                st.success("Kayıt başarılı! Şimdi 'Giriş Yap' sekmesinden giriş yapabilirsiniz.")

else:
    user_id = st.session_state.user["id"]
    user_name = st.session_state.user["ad_soyad"]
    package = st.session_state.user["paket"]
    is_admin = st.session_state.user["is_admin"]

    if st.session_state.get('active_conv_id') is None:
        existing = get_conversations(user_id)
        if existing:
            st.session_state.active_conv_id = existing[0][0]
        else:
            st.session_state.active_conv_id = create_conversation(user_id, "Yeni Sohbet")

    with st.sidebar:
        st.header(f"👤 {user_name}")
        st.write(f"Paket: {package}")
        if st.button("Çıkış Yap"):
            st.session_state.logged_in = False
            st.session_state.active_conv_id = None
            st.rerun()

        st.divider()
        if st.button("➕ Yeni Sohbet"):
            st.session_state.active_conv_id = create_conversation(user_id, "Yeni Sohbet")
            st.rerun()

        st.subheader("🕘 Geçmiş Sohbetler")
        for conv_id, title in get_conversations(user_id):
            label = title if conv_id != st.session_state.active_conv_id else f"➡️ {title}"
            if st.button(label, key=f"conv_{conv_id}"):
                st.session_state.active_conv_id = conv_id
                st.rerun()

        if package == "Pro" or is_admin:
            st.divider()
            st.subheader("⚙️ Özelleştirme")
            current_instr = get_custom_instructions(user_id)
            new_instr = st.text_area(
                "Asistan senin için nasıl davransın?",
                value=current_instr, height=150, key="custom_instr_box",
            )
            if st.button("Kaydet", key="save_instr"):
                set_custom_instructions(user_id, new_instr)
                st.success("Kaydedildi.")

        if is_admin:
            st.divider()
            if st.checkbox("Admin Panelini Göster"):
                users = get_all_users()
                st.write("### Kullanıcılar")
                for uid, uemail, uad, upaket, ucreated in users:
                    col1, col2, col3 = st.columns([2, 1, 1])
                    col1.write(f"{uad} ({uemail})")
                    new_paket = col2.selectbox(
                        "Paket", ["Ücretsiz", "Pro", "Admin"],
                        index=["Ücretsiz", "Pro", "Admin"].index(upaket) if upaket in ["Ücretsiz", "Pro", "Admin"] else 0,
                        key=f"paket_{uid}", label_visibility="collapsed",
                    )
                    if col3.button("Güncelle", key=f"update_{uid}"):
                        update_user_package(uid, new_paket)
                        st.rerun()

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
                custom_instructions = get_custom_instructions(user_id) if (package == "Pro" or is_admin) else ""
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
