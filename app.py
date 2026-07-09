import streamlit as st
import pandas as pd

# Google Sheets ID'n
SHEET_ID = "1zsOjvvXjbLBOr3b2bqtuSDXpea3Sp2Pg0AIgXk-sJic"
URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Sayfa1"

def load_data():
    return pd.read_csv(URL)

st.title("RE-OS Intelligence - Yönetim Paneli")
code = st.text_input("Erişim Kodunu Gir:")

# Veriyi çek
df = load_data()

if code:
    match = df[df['Kod'] == code]
    if not match.empty:
        st.success(f"Hoş geldin! {match.iloc[0]['MusteriAdi']} - {match.iloc[0]['PaketTuru']}")
        
        # Mertnine9 için Admin Paneli
        if code == 'Mertnine9':
            st.write("---")
            st.subheader("Admin Paneli Aktif")
            st.write("Sistem tıkır tıkır çalışıyor.")
    else:
        st.error("Kod hatalı!")

