import streamlit as st
import google.generativeai as genai
import json
import os
import re
import requests
from datetime import datetime
from docxtpl import DocxTemplate
from thefuzz import process

# ================= KONFIGURASI (DIAMBIL DARI STREAMLIT SECRETS) =================
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
ADMIN_ID = "416111259"

TEMPLATE_FILENAME = "template_sk.docx"
DATABASE_DOSEN_FILE = "dosen.json"

st.set_page_config(page_title="SK Pembimbing", page_icon="🎓", layout="centered")

# CSS Styling (Untuk kerapian di HP)
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; font-weight: bold; }
    .stExpander { border-radius: 10px; }
    h1 { font-size: 1.8rem !important; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# Setup AI (KOREKSI: Menggunakan nama alias model yang berbeda)
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash") # <--- KOREKSI DI SINI
except Exception as e:
    st.error(f"❌ Error Setup AI. Cek GEMINI_API_KEY di Secrets: {e}")

# ================= FUNGSI TELEGRAM =================
def kirim_ke_admin_telegram(file_path, data_mhs):
    clean_token = TELEGRAM_TOKEN.strip()
    url = f"https://api.telegram.org/bot{clean_token}/sendDocument"
    
    nomor_wa = data_mhs['wa'].strip()
    if nomor_wa.startswith("0"): wa_link = "62" + nomor_wa[1:]
    elif nomor_wa.startswith("62"): wa_link = nomor_wa
    else: wa_link = "62" + nomor_wa
    
    caption = (
        f"🚨 **PENGAJUAN SK VIA WEB**\n\n"
        f"👤 Nama: {data_mhs['nama']}\n"
        f"🆔 NIM: {data_mhs['nim']}\n"
        f"📱 WA: [{nomor_wa}](https://wa.me/{wa_link}) (Klik untuk kirim PDF)\n\n"
        f"👉 Silakan TTE file ini, lalu kirim PDF-nya ke mahasiswa via Link WA di atas."
    )
    
    try:
        with open(file_path, 'rb') as f:
            payload = {'chat_id': ADMIN_ID, 'caption': caption, 'parse_mode': 'Markdown'}
            files = {'document': f}
            resp = requests.post(url, data=payload, files=files)
            if resp.status_code == 200: return True, "Berhasil"
            else: return False, f"Error Telegram ({resp.status_code}): {resp.text}"
    except Exception as e:
        return False, f"Error Sistem: {str(e)}"

# ================= FUNGSI HELPER LAINNYA =================
def load_database_dosen():
    if os.path.exists(DATABASE_DOSEN_FILE):
        try:
            with open(DATABASE_DOSEN_FILE, 'r') as f: return json.load(f)
        except: return []
    return []

def cari_dosen_termirip(nama_input):
    db_dosen = load_database_dosen()
    if not db_dosen or not nama_input: return nama_input
    hasil, skor = process.extractOne(nama_input, db_dosen)
    if skor > 65: return hasil
    return nama_input

def format_sem(angka):
    romawi = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV"]
    kata = ["", "Satu", "Dua", "Tiga", "Empat", "Lima", "Enam", "Tujuh", "Delapan", "Sembilan", "Sepuluh", "Sebelas", "Dua Belas", "Tiga Belas", "Empat Belas"]
    try:
        idx = int(angka)
        if 0 < idx < 15: return f"{romawi[idx]} ({kata[idx]})"
        return str(idx)
    except: return str(angka)

def hitung_sem(nim):
    try:
        thn = 2000 + int(nim[:2])
        now = datetime.now()
        sem = (now.year - thn) * 2
        if now.month >= 9 or now.month <= 2: sem += 1
        return max(1, sem)
    except: return 1

def clean_json(txt):
    m = re.search(r'\{.*\}', txt, re.DOTALL)
    if m: return json.loads(m.group(0))
    return None

# ================= FUNGSI AI (HANYA FLASH) =================

def ai_cover(path):
    prompt = """Analisis Cover. Ambil: 1.Judul(KAPITAL), 2.Nama(Bersih), 3.NIM(Angka), 4.Prodi. JSON: {"judul":"..","nama":"..","nim":"..","prodi":".."}"""
    try:
        f_ai = genai.upload_file(path)
        res = model.generate_content([f_ai, prompt])
        return clean_json(res.text)
    except: return None

def ai_wadek(path):
    prompt = """Analisis tulisan tangan. Cari Pembimbing 1 & 2. JSON: {"pb1":"..","pb2":".."}"""
    try:
        f_ai = genai.upload_file(path)
        res = model.generate_content([f_ai, prompt])
        return clean_json(res.text)
    except: return None

# ================= UI APLIKASI =================

st.title("🎓 SK Pembimbing")
st.caption("Fakultas Tarbiyah & Ilmu Keguruan")

# Init Session
if 'data' not in st.session_state: 
    st.session_state.data = {'nama': '', 'nim': '', 'judul': '', 'prodi': '', 'sem': '', 'pb1': '', 'pb2': '', 'wa': ''}

# --- BAGIAN 0: INPUT WA ---
st.info("📱 **Data Kontak**")
wa_input = st.text_input("Nomor WhatsApp (Contoh: 08123456789)", st.session_state.data['wa'])
st.session_state.data['wa'] = wa_input

# --- BAGIAN 1: COVER ---
st.markdown("---")
st.info("📸 **Langkah 1: Foto Cover Proposal**")
input_method = st.radio("Input Cover:", ["📁 Galeri", "📷 Kamera"], horizontal=True, label_visibility="collapsed")
img_file = st.file_uploader("Upload Cover", type=["jpg","png","jpeg"]) if input_method == "📁 Galeri" else st.camera_input("Jepret Cover")

if img_file:
    if st.button("🔍 Baca Cover"):
        with st.spinner("Membaca..."):
            with open("temp.jpg", "wb") as f: f.write(img_file.getbuffer())
            try:
                json_res = ai_cover("temp.jpg")
                if json_res:
                    st.session_state.data.update({
                        'nama': json_res.get('nama', ''), 'judul': json_res.get('judul', ''),
                        'prodi': json_res.get('prodi', 'Manajemen Pendidikan Islam'),
                        'nim': str(json_res.get('nim', '')).replace(" ", "")
                    })
                    st.session_state.data['sem'] = format_sem(hitung_sem(st.session_state.data['nim']))
                    st.success("Cover Terbaca!")
            except Exception as e: st.error(f"Error: {e}")

with st.expander("📝 Cek Data Identitas", expanded=True):
    st.session_state.data['nama'] = st.text_input("Nama", st.session_state.data['nama'])
    c1, c2 = st.columns(2)
    with c1: st.session_state.data['nim'] = st.text_input("NIM", st.session_state.data['nim'])
    with c2: st.session_state.data['sem'] = st.text_input("Semester", st.session_state.data['sem'])
    st.session_state.data['prodi'] = st.text_input("Prodi", st.session_state.data['prodi'])
    st.session_state.data['judul'] = st.text_area("Judul", st.session_state.data['judul'])

# --- BAGIAN 2: WADEK ---
st.markdown("---")
st.info("📸 **Langkah 2: Foto Catatan Wadek**")
input_wd = st.radio("Input Wadek:", ["📁 Galeri ", "📷 Kamera "], horizontal=True, label_visibility="collapsed")
wd_file = st.file_uploader("Upload Wadek", type=["jpg","png","jpeg"], key="wd_up") if input_wd == "📁 Galeri " else st.camera_input("Jepret Wadek", key="wd_cam")

if wd_file:
    if st.button("🧠 Cek Pembimbing"):
        with st.spinner("Analisis Dosen & Mencocokkan Database..."):
            with open("temp_wd.jpg", "wb") as f: f.write(wd_file.getbuffer())
            try:
                json_res = clean_json(model.generate_content([genai.upload_file("temp_wd.jpg"), "Analisis tulisan tangan. Cari Pembimbing 1 & 2. JSON: {\"pb1\":\"..\",\"pb2\":\"..\"}"]).text)
                if json_res:
                    st.session_state.data['pb1'] = cari_dosen_termirip(json_res.get('pb1', ''))
                    st.session_state.data['pb2'] = cari_dosen_termirip(json_res.get('pb2', ''))
                    st.success("Dosen Ditemukan!")
            except Exception as e: st.error(f"Error: {e}")

with st.expander("👨‍🏫 Cek Pembimbing", expanded=True):
    st.session_state.data['pb1'] = st.text_input("Pembimbing 1", st.session_state.data['pb1'])
    st.session_state.data['pb2'] = st.text_input("Pembimbing 2", st.session_state.data['pb2'])

# --- BAGIAN 3: EKSEKUSI ---
st.markdown("---")
col_btn1, col_btn2 = st.columns(2)

# Tombol 1: Hanya Download
with col_btn1:
    if st.button("📄 Generate Draft"):
        d = st.session_state.data
        if not d['nama']: st.warning("Nama Kosong!")
        elif not os.path.exists(TEMPLATE_FILENAME): st.error("Template Hilang!")
        else:
            try:
                doc = DocxTemplate(TEMPLATE_FILENAME)
                now = datetime.now()
                bln_indo = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
                bln_rom = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
                ctx = {
                    'nama': d['nama'], 'nim': d['nim'], 'semester': d['sem'],
                    'prodi': d['prodi'], 'judul': d['judul'],
                    'pembimbing1': d['pb1'], 'pembimbing2': d['pb2'],
                    'tanggal': f"Ternate, {now.day} {bln_indo[now.month-1]} {now.year}",
                    'bulan': bln_rom[now.month-1]
                }
                doc.render(ctx)
                out = f"SK_{d['nim']}.docx"
                doc.save(out)
                with open(out, "rb") as f:
                    st.download_button("⬇️ Download di HP", f, file_name=out)
            except Exception as e: st.error(f"Gagal generate: {e}")

# Tombol 2: KIRIM KE ADMIN
with col_btn2:
    if st.button("🚀 KIRIM KE ADMIN", type="primary"):
        if not st.session_state.data['wa']: st.warning("⚠️ Isi Nomor WA!")
        elif not st.session_state.data['nama']: st.warning("⚠️ Data belum lengkap!")
        else:
            with st.spinner("Sedang mengirim ke Telegram Admin..."):
                d = st.session_state.data
                try:
                    # 1. Generate Dokumen
                    doc = DocxTemplate(TEMPLATE_FILENAME)
                    now = datetime.now()
                    bln_indo = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
                    bln_rom = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
                    ctx = {
                        'nama': d['nama'], 'nim': d['nim'], 'semester': d['sem'], 'prodi': d['prodi'], 'judul': d['judul'],
                        'pembimbing1': d['pb1'], 'pembimbing2': d['pb2'], 'tanggal': f"Ternate, {now.day} {bln_indo[now.month-1]} {now.year}",
                        'bulan': bln_rom[now.month-1]
                    }
                    doc.render(ctx)
                    out = f"SK_{d['nim']}.docx"
                    doc.save(out)
                except Exception as e:
                    st.error(f"❌ Gagal Generate Dokumen: {e}")
                    pass # Lanjut ke pengiriman, dokumen tetap ada di server

                # 2. Kirim ke Telegram
                sukses, pesan_info = kirim_ke_admin_telegram(out, d)
                
                if sukses:
                    st.success("✅ BERHASIL! Surat sudah masuk ke Telegram Admin.")
                    st.info("Tunggu Admin mengirim file PDF yang sudah ditanda tangani ke WhatsApp Anda.")
                    st.balloons()
                else:
                    st.error(f"❌ GAGAL KIRIM: {pesan_info}")
                    st.warning("Tips: Cek TELEGRAM_TOKEN dan ADMIN_ID di Secrets Anda.")
