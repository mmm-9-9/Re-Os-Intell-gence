import os
import re
import secrets
import hashlib
import datetime
import requests
import psycopg2
import streamlit as st
from google import genai
from google.genai import types
import pandas as pd

# ============ AYARLAR ============
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    st.error("GEMINI_API_KEY ortam değişkeni bulunamadı. Render > Environment kısmından ekleyin.")
    st.stop()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    st.error("DATABASE_URL ortam değişkeni bulunamadı. Render > Environment kısmından ekleyin.")
    st.stop()

client = genai.Client(api_key=API_KEY)
MODEL_NAME = "gemini-3.5-flash"

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower()

st.set_page_config(page_title="ReOs Intelligence", layout="wide")


# ============ VERİTABANI (Postgres / Supabase) ============
def get_conn():
    return psycopg2.connect(DATABASE_URL)


def run(sql, params=None, fetch=False, returning=False):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params or ())
    result = None
    if fetch:
        result = cur.fetchall()
    elif returning:
        result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return result


def init_db():
    run("""CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        ad_soyad TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        paket TEXT NOT NULL DEFAULT 'Ücretsiz',
        is_admin INTEGER NOT NULL DEFAULT 0,
        sehir TEXT NOT NULL DEFAULT 'Bursa',
        created_at TEXT NOT NULL
    )""")
    run("""CREATE TABLE IF NOT EXISTS conversations (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    run("""CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        conversation_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        ts TEXT NOT NULL
    )""")
    run("""CREATE TABLE IF NOT EXISTS user_settings (
        user_id INTEGER PRIMARY KEY,
        custom_instructions TEXT
    )""")
    run("""CREATE TABLE IF NOT EXISTS user_memory (
        user_id INTEGER PRIMARY KEY,
        notes TEXT
    )""")


init_db()


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
    rows = run(
        "SELECT id, email, ad_soyad, password_hash, salt, paket, is_admin, sehir FROM users WHERE email = %s",
        (email.strip().lower(),), fetch=True
    )
    return rows[0] if rows else None


def create_user(email, ad_soyad, password, sehir):
    email = email.strip().lower()
    pwd_hash, salt = hash_password(password)
    is_admin = 1 if (ADMIN_EMAIL and email == ADMIN_EMAIL) else 0
    paket = "Admin" if is_admin else "Ücretsiz"
    run(
        "INSERT INTO users (email, ad_soyad, password_hash, salt, paket, is_admin, sehir, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (email, ad_soyad, pwd_hash, salt, paket, is_admin, sehir.strip() or "Bursa", datetime.datetime.now().isoformat())
    )


def get_all_users():
    return run("SELECT id, email, ad_soyad, paket, created_at FROM users ORDER BY id", fetch=True)


def update_user_package(user_id, paket):
    run("UPDATE users SET paket = %s WHERE id = %s", (paket, user_id))


# ============ SOHBET VERİTABANI ============
def create_conversation(user_id, title):
    row = run(
        "INSERT INTO conversations (user_id, title, created_at) VALUES (%s, %s, %s) RETURNING id",
        (user_id, title, datetime.datetime.now().isoformat()), returning=True
    )
    return row[0]


def get_conversations(user_id):
    return run("SELECT id, title FROM conversations WHERE user_id = %s ORDER BY id DESC", (user_id,), fetch=True)


def rename_conversation(conv_id, title):
    run("UPDATE conversations SET title = %s WHERE id = %s", (title, conv_id))


def delete_conversation(conv_id):
    run("DELETE FROM messages WHERE conversation_id = %s", (conv_id,))
    run("DELETE FROM conversations WHERE id = %s", (conv_id,))


def delete_all_conversations(user_id):
    conv_ids = run("SELECT id FROM conversations WHERE user_id = %s", (user_id,), fetch=True)
    for (conv_id,) in conv_ids:
        run("DELETE FROM messages WHERE conversation_id = %s", (conv_id,))
    run("DELETE FROM conversations WHERE user_id = %s", (user_id,))


def add_message(conv_id, role, content):
    run(
        "INSERT INTO messages (conversation_id, role, content, ts) VALUES (%s, %s, %s, %s)",
        (conv_id, role, content, datetime.datetime.now().isoformat())
    )


def get_messages(conv_id):
    rows = run("SELECT role, content FROM messages WHERE conversation_id = %s ORDER BY id ASC", (conv_id,), fetch=True)
    return [{"role": r, "content": c} for r, c in rows]


def get_custom_instructions(user_id):
    rows = run("SELECT custom_instructions FROM user_settings WHERE user_id = %s", (user_id,), fetch=True)
    return rows[0][0] if rows and rows[0][0] else ""


def set_custom_instructions(user_id, text):
    run(
        "INSERT INTO user_settings (user_id, custom_instructions) VALUES (%s, %s) "
        "ON CONFLICT (user_id) DO UPDATE SET custom_instructions = EXCLUDED.custom_instructions",
        (user_id, text)
    )


# ============ KALICI HAFIZA (sohbetler arası hatırlama) ============
def get_memory(user_id):
    rows = run("SELECT notes FROM user_memory WHERE user_id = %s", (user_id,), fetch=True)
    return rows[0][0] if rows and rows[0][0] else ""


def save_memory(user_id, notes):
    run(
        "INSERT INTO user_memory (user_id, notes) VALUES (%s, %s) "
        "ON CONFLICT (user_id) DO UPDATE SET notes = EXCLUDED.notes",
        (user_id, notes)
    )


def update_memory_from_exchange(user_id, user_msg, assistant_msg):
    """Konuşmadan kalıcı, durable bilgi çıkarıp hafızaya ekler. Hata olursa sohbeti bozmasın diye sessizce geçer."""
    try:
        existing = get_memory(user_id)
        extraction_prompt = (
            "Aşağıda bir kullanıcının asistanla yaptığı mesaj alışverişi var. "
            "Görevin: kullanıcı hakkında GELECEKTE de geçerli olacak, kalıcı bilgileri "
            "(iş, tercihler, tekrar eden konular, isimler, hedefler vb.) çıkarıp mevcut "
            "notlara eklemek/güncellemek. Geçici, o ana özel bilgileri (bugün ne sordu gibi) EKLEME. "
            "Sadece kısa madde işaretli bir liste döndür, başka hiçbir açıklama yazma. "
            "Eğer bu alışverişte kalıcı bir bilgi yoksa, mevcut notları olduğu gibi döndür.\n\n"
            f"MEVCUT NOTLAR:\n{existing if existing else '(henüz not yok)'}\n\n"
            f"YENİ MESAJ:\nKullanıcı: {user_msg}\nAsistan: {assistant_msg}\n\n"
            "GÜNCELLENMİŞ NOTLAR:"
        )
        response = client.models.generate_content(model=MODEL_NAME, contents=extraction_prompt)
        new_notes = response.text.strip()
        if new_notes:
            save_memory(user_id, new_notes)
    except Exception:
        pass


# ============ ASİSTAN YARDIMCILARI ============
def get_weather_for_city(sehir):
    sehir = (sehir or "Bursa").strip()
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": sehir, "count": 1, "language": "tr"},
            timeout=5,
        ).json()
        if not geo.get("results"):
            return f"'{sehir}' için hava durumu bulunamadı."
        lat = geo["results"][0]["latitude"]
        lon = geo["results"][0]["longitude"]
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current": "temperature_2m,weather_code", "timezone": "auto"},
            timeout=5,
        )
        data = r.json()
        temp = data["current"]["temperature_2m"]
        return f"{sehir}'da şu an hava yaklaşık {temp}°C."
    except Exception:
        return "Hava durumu bilgisi şu an alınamadı."


def build_system_prompt(custom_instructions, sehir, memory_notes=""):
    now = datetime.datetime.now()
    gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    aylar = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
             "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    tarih_str = f"{now.day} {aylar[now.month-1]} {now.year}, {gunler[now.weekday()]}"
    hava = get_weather_for_city(sehir)
    prompt = (
        "Sen ReOs adında, kullanıcıya yardımcı olan uzman bir kişisel asistansın. "
        "Net, kısa ve faydalı cevaplar ver.\n\n"
        f"Bugünün tarihi: {tarih_str}.\n"
        f"Güncel hava durumu: {hava}\n"
    )
    if memory_notes and memory_notes.strip():
        prompt += f"\nBu kullanıcı hakkında önceki sohbetlerden hatırladığın bilgiler:\n{memory_notes.strip()}\n"
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
                    "paket": user[5], "is_admin": bool(user[6]), "sehir": user[7],
                }
                st.session_state.active_conv_id = None
                st.rerun()
            else:
                st.error("Email veya şifre hatalı.")

    with tab_kayit:
        yeni_ad = st.text_input("Ad Soyad", key="reg_ad")
        yeni_email = st.text_input("Email", key="reg_email")
        yeni_sehir = st.text_input("Yaşadığınız şehir", key="reg_sehir", placeholder="Örn: Bursa")
        yeni_pw = st.text_input("Şifre", type="password", key="reg_pw")
        yeni_pw2 = st.text_input("Şifre (tekrar)", type="password", key="reg_pw2")
        if st.button("Kayıt Ol"):
            if not yeni_ad.strip():
                st.error("Ad soyad giriniz.")
            elif not email_valid(yeni_email):
                st.error("Geçerli bir email giriniz.")
            elif not yeni_sehir.strip():
                st.error("Şehir giriniz.")
            elif len(yeni_pw) < 6:
                st.error("Şifre en az 6 karakter olmalı.")
            elif yeni_pw != yeni_pw2:
                st.error("Şifreler eşleşmiyor.")
            elif get_user_by_email(yeni_email):
                st.error("Bu email zaten kayıtlı.")
            else:
                create_user(yeni_email, yeni_ad.strip(), yeni_pw, yeni_sehir.strip())
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
        conv_list = get_conversations(user_id)
        for conv_id, title in conv_list:
            label = title if conv_id != st.session_state.active_conv_id else f"➡️ {title}"
            col_a, col_b = st.columns([4, 1])
            if col_a.button(label, key=f"conv_{conv_id}"):
                st.session_state.active_conv_id = conv_id
                st.rerun()
            if col_b.button("🗑️", key=f"del_{conv_id}"):
                delete_conversation(conv_id)
                if st.session_state.active_conv_id == conv_id:
                    st.session_state.active_conv_id = None
                st.rerun()

        if len(conv_list) > 1:
            if st.button("🗑️ Tüm Sohbetleri Sil"):
                delete_all_conversations(user_id)
                st.session_state.active_conv_id = None
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
                memory_notes = get_memory(user_id)
                system_prompt = build_system_prompt(custom_instructions, st.session_state.user["sehir"], memory_notes)
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
                update_memory_from_exchange(user_id, prompt, answer)
            except Exception as e:
                st.error(f"Hata: {e}")
