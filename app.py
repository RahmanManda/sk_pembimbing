import streamlit as st
import google.generativeai as genai
import json
import os
import re
import requests
from datetime import datetime
from docxtpl import DocxTemplate
from thefuzz import process

# ================= KONFIGURASI =================
try:
    TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] 
except:
    st.error("Error: Cek secrets.toml. Pastikan TELEGRAM_TOKEN dan GEMINI_API_KEY sudah ada.")
    st.stop()

# ID GRUP ADMIN (Sudah disesuaikan ke grup)
GROUP_CHAT_ID = "-5193774282" 
TEMPLATE_FILENAME = "template_sk.docx"
DATABASE_DOSEN_FILE = "dosen.json"

st.set_page_config(page_title="SK Pembimbing", page_icon="🎓", layout="centered")

# CSS Agar Tampilan Rapi
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; font-weight: bold; }
    .stExpander { border-radius: 10px; }
    h1 { font-size: 1.8rem !important; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# Setup AI
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
except Exception as e:
    st.error(f"❌ Error Setup AI: {e}")

# ================= FUNGSI HELPER =================

def format_sem_otomatis(angka):
    """Mengubah angka '7' menjadi 'VII (Tujuh)'"""
    try:
        n = int(angka)
        rom = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV"]
        txt = ["", "Satu", "Dua", "Tiga", "Empat", "Lima", "Enam", "Tujuh", "Delapan", "Sembilan", "Sepuluh", "Sebelas", "Dua Belas", "Tiga Belas", "Empat Belas"]
        if 0 < n < 15:
            return f"{rom[n]} ({txt[n]})"
        return str(angka)
    except:
        return str(angka)

def kirim_ke_grup_telegram(file_path, data_mhs):
    clean_token = TELEGRAM_TOKEN.strip()
    url = f"https://api.telegram.org/bot{clean_token}/sendDocument"
    
    wa = data_mhs['wa'].strip()
    wa_link = "62" + wa[1:] if wa.startswith("0") else (wa if wa.startswith("62") else "62" + wa)
    
    # Caption dipertegas agar Admin grup bisa membedakan jenis surat
    caption = (
        f"🎓 **[PENGAJUAN SK PEMBIMBING]** 🎓\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Nama:** {data_mhs['nama'].upper()}\n"
        f"🆔 **NIM:** {data_mhs['nim']}\n"
        f"📚 **Prodi:** {data_mhs['prodi']}\n"
        f"👨‍🏫 **PB 1:** {data_mhs['pb1']}\n"
        f"👨‍🏫 **PB 2:** {data_mhs['pb2']}\n"
        f"📱 **WA:** [Hubungi Mahasiswa](https://wa.me/{wa_link})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👉 *Admin: Mohon segera proses SK Penunjukan Pembimbing ini.*"
    )
    
    try:
        with open(file_path, 'rb') as f:
            payload = {'chat_id': GROUP_CHAT_ID, 'caption': caption, 'parse_mode': 'Markdown'}
            resp = requests.post(url, data=payload, files={'document': f})
            if resp.status_code == 200: return True, "OK"
            return False, f"Telegram Error: {resp.text}"
    except Exception as e:
        return False, str(e)

def clean_json(txt):
    m = re.search(r'\{.*\}', txt, re.DOTALL)
    if m: return json.loads(m.group(0))
    return None

def cari_dosen(nama):
    if not os.path.exists(DATABASE_DOSEN_FILE): return nama
    try:
        with open(DATABASE_DOSEN_FILE, 'r', encoding='utf-8') as f: db = json.load(f)
        res, skor = process.extractOne(nama, db)
        return res if skor > 65 else nama
    except:
        return nama

# ================= UI APLIKASI =================
st.title("🎓 SK Pembimbing")
st.caption("Fakultas Tarbiyah & Ilmu Keguruan")

if 'data' not in st.session_state: 
    st.session_state.data = {'nama': '', 'nim': '', 'sem': '', 'prodi': '', 'judul': '', 'pb1': '', 'pb2': '', 'wa': ''}

d = st.session_state.data

# 1. INPUT WA
st.info("📱 **Kontak Mahasiswa**")
d['wa'] = st.text_input("Nomor WhatsApp (Wajib)", d['wa'])

# 2. INPUT COVER (SCAN AI)
st.markdown("---")
st.info("📸 **Identitas & Judul**")
with st.expander("Buka Kamera / Upload Cover"):
    src_cv = st.radio("Sumber:", ["📁 Upload", "📷 Kamera"], horizontal=True, key="src_cv", label_visibility="collapsed")
    img_cv = st.file_uploader("File Cover", ["jpg","png"]) if src_cv == "📁 Upload" else st.camera_input("Foto Cover")

    if img_cv and st.button("🔍 Scan Cover Otomatis"):
        with st.spinner("AI sedang membaca..."):
            with open("temp.jpg", "wb") as f: f.write(img_cv.getbuffer())
            try:
                f_ai = genai.upload_file("temp.jpg")
                prompt = """Analisis Cover Skripsi ini. Ambil data JSON: {"judul":"..","nama":"..","nim":"..","prodi":".."}"""
                res = model.generate_content([f_ai, prompt])
                js = clean_json(res.text)
                if js:
                    d.update(js)
                    d['nim'] = str(js.get('nim','')).replace(" ","")
                    st.success("Cover terbaca! Silakan cek di bawah.")
                    st.rerun()
            except Exception as e:
                st.error(f"Gagal baca cover: {e}")

# FORM MANUAL (Override)
d['nama'] = st.text_input("Nama", d['nama'])
c1, c2 = st.columns(2)
with c1: d['nim'] = st.text_input("NIM", d['nim'])
with c2: d['sem'] = st.text_input("Semester (Angka)", d['sem'])
d['prodi'] = st.text_input("Prodi", d.get('prodi', 'Manajemen Pendidikan Islam'))
d['judul'] = st.text_area("Judul", d['judul'])


# 3. INPUT WADEK (SCAN AI)
st.markdown("---")
st.info("👨‍🏫 **Pembimbing (Catatan Wadek)**")
with st.expander("Buka Kamera / Upload Catatan"):
    src_wd = st.radio("Sumber:", ["📁 Upload", "📷 Kamera"], horizontal=True, key="src_wd", label_visibility="collapsed")
    img_wd = st.file_uploader("File Wadek", ["jpg","png"]) if src_wd == "📁 Upload" else st.camera_input("Foto Wadek")

    if img_wd and st.button("🧠 Scan Tulisan Wadek"):
        with st.spinner("Membaca tulisan tangan..."):
            with open("temp_wd.jpg", "wb") as f: f.write(img_wd.getbuffer())
            try:
                f_ai = genai.upload_file("temp_wd.jpg")
                prompt = """Baca tulisan tangan ini. Cari nama 2 dosen pembimbing. JSON: {"pb1":"Nama Dosen 1","pb2":"Nama Dosen 2"}"""
                res = model.generate_content([f_ai, prompt])
                js = clean_json(res.text)
                if js:
                    d['pb1'] = cari_dosen(js.get('pb1',''))
                    d['pb2'] = cari_dosen(js.get('pb2',''))
                    st.success("Dosen terbaca!")
                    st.rerun()
            except Exception as e:
                st.error(f"Gagal baca dosen: {e}")

d['pb1'] = st.text_input("Pembimbing 1", d['pb1'])
d['pb2'] = st.text_input("Pembimbing 2", d['pb2'])

# 4. TOMBOL KIRIM
st.markdown("---")
if st.button("🚀 KIRIM KE GRUP ADMIN", type="primary"):
    if not d['wa'] or not d['nama']:
        st.warning("⚠️ Nama dan Nomor WA wajib diisi!")
    else:
        with st.spinner("Mengirim ke Grup Telegram..."):
            try:
                now = datetime.now()
                bln = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
                rom_bln = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
                
                txt_semester = format_sem_otomatis(d['sem'])
                
                ctx = {
                    'nama': d['nama'].upper(),
                    'nim': d['nim'], 
                    'semester': txt_semester,
                    'prodi': d['prodi'].upper(),
                    'judul': d['judul'].upper(),
                    'pembimbing1': d['pb1'], 
                    'pembimbing2': d['pb2'],
                    'tanggal': f"Ternate, {now.day} {bln[now.month-1]} {now.year}",
                    'bulan': rom_bln[now.month-1]
                }
                
                doc = DocxTemplate(TEMPLATE_FILENAME)
                doc.render(ctx)
                
                # Penamaan file agar jelas ini SK Pembimbing
                nama_depan = d['nama'].strip().split()[0]
                nama_clean = "".join(x for x in nama_depan if x.isalnum())
                out = f"SK_Pembimbing_{nama_clean}.docx" 

                doc.save(out)
                
                # Kirim ke Telegram Grup
                sukses, msg = kirim_ke_grup_telegram(out, d)
                if sukses:
                    st.balloons()
                    st.success(f"✅ BERHASIL! File '{out}' sudah masuk ke Grup Admin.")
                    if os.path.exists(out): os.remove(out)
                else:
                    st.error(f"❌ Gagal Kirim ke Grup: {msg}")
            except Exception as e:
                st.error(f"System Error: {e}")
