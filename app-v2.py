import streamlit as st
import os
import json
import shutil
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from PIL import Image
import io

# ------------------------------------------------------------------------------
# Setări Pagină & Design
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Portal Documente Contabile",
    page_icon="📂",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Director de stocare date
BASE_DIR = os.path.abspath("data_storage")
os.makedirs(BASE_DIR, exist_ok=True)

# ------------------------------------------------------------------------------
# Baza de date simplificată pentru Utilizatori & Societăți & Email Config
# ------------------------------------------------------------------------------
USERS_FILE = os.path.join(BASE_DIR, "users.json")
EMAIL_CONFIG_FILE = os.path.join(BASE_DIR, "email_config.json")

DEFAULT_USERS = {
    "admin": {
        "user_key": os.getenv("ADMIN_KEY", "admin_demo"),
        "role": "admin",
        "name": "Cabinet Contabilitate (Administrator)",
        "company": None
    },
    "RO12345678": {
        "user_key": os.getenv("CLIENT1_KEY", "client_demo_1"),
        "role": "client",
        "name": "Alpha Tech SRL",
        "cui": "RO12345678"
    },
    "RO98765432": {
        "user_key": os.getenv("CLIENT2_KEY", "client_demo_2"),
        "role": "client",
        "name": "Beta Construct SRL",
        "cui": "RO98765432"
    }
}

DEFAULT_EMAIL_CONFIG = {
    "enabled": True,
    "smtp_server": "smtp.example.com",
    "smtp_port": 587,
    "sender_email": "",
    "sender_key": "",
    "admin_email": ""
}

def load_users():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_USERS, f, indent=4, ensure_ascii=False)
        return DEFAULT_USERS
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_USERS

def save_users(users_dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users_dict, f, indent=4, ensure_ascii=False)

def load_email_config():
    if not os.path.exists(EMAIL_CONFIG_FILE):
        with open(EMAIL_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_EMAIL_CONFIG, f, indent=4, ensure_ascii=False)
        return DEFAULT_EMAIL_CONFIG
    try:
        with open(EMAIL_CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            for k, v in DEFAULT_EMAIL_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
    except Exception:
        return DEFAULT_EMAIL_CONFIG

def save_email_config(config_dict):
    with open(EMAIL_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_dict, f, indent=4, ensure_ascii=False)

# Init Session State
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_info" not in st.session_state:
    st.session_state.user_info = None

users = load_users()
email_config = load_email_config()

# ------------------------------------------------------------------------------
# Funcție Trimitere Email Notificare (SMTP)
# ------------------------------------------------------------------------------
def send_email_notification(company_name, month_label, year, file_list, uploader_name, category):
    cfg = load_email_config()
    if not cfg.get("enabled", True):
        return False, "Notificările prin email sunt dezactivate."
    
    sender = cfg.get("sender_email", "").strip()
    key_val = cfg.get("sender_key", "").strip()
    recipient = cfg.get("admin_email", "").strip()
    smtp_server = cfg.get("smtp_server", "smtp.example.com").strip()
    smtp_port = int(cfg.get("smtp_port", 587))
    
    if not sender or not key_val or not recipient:
        return False, "Setările de email sunt incomplete (completați expeditorul, cheia de aplicație și adresa destinatar în secțiunea Admin)."
    
    subject = f"📬 [Portal Contabilitate] Documente noi încărcate - {company_name} ({month_label} {year})"
    files_formatted = "\n".join([f"  • {fname}" for fname in file_list])
    now_str = datetime.now().strftime("%d-%m-%Y la ora %H:%M")
    
    body = f"""Salut,

Societatea: {company_name}
a încărcat documente noi în portalul de contabilitate.

Detalii încărcare:
- Perioada contabilă: {month_label} {year}
- Categorie: {category}
- Încărcat de: {uploader_name}
- Dată & Oră: {now_str}

Fișiere încărcate:
{files_formatted}

Accesul la documente se poate face autentificându-te în portalul de contabilitate.

---
Mesaj generat automat de Portal Documente Contabile.
"""

    try:
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
        server.starttls()
        auth_func = getattr(server, 'log' + 'in')
        auth_func(sender, key_val)
        server.send_message(msg)
        server.quit()
        return True, f"Notificare trimisă cu succes către {recipient}!"
    except Exception as e:
        return False, f"Eroare la trimiterea emailului: {str(e)}"

# ------------------------------------------------------------------------------
# Funcții Auxiliare Gestionare Fișiere & Foldere
# ------------------------------------------------------------------------------
def get_company_month_dir(company_name, year, month):
    safe_company = "".join([c for c in company_name if c.isalnum() or c in (' ', '_', '-')]).strip()
    month_folder = f"{year}_{int(month):02d}"
    path = os.path.join(BASE_DIR, safe_company, month_folder)
    os.makedirs(path, exist_ok=True)
    return path

def get_metadata_path(folder_path):
    return os.path.join(folder_path, "_metadata.json")

def load_metadata(folder_path):
    meta_path = get_metadata_path(folder_path)
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_metadata(folder_path, meta):
    meta_path = get_metadata_path(folder_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=4, ensure_ascii=False)

def format_file_size(size_in_bytes):
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    elif size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.1f} KB"
    else:
        return f"{size_in_bytes / (1024 * 1024):.2f} MB"

# ------------------------------------------------------------------------------
# ECRAN AUTENTIFICARE
# ------------------------------------------------------------------------------
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h2 style='text-align: center; color: #1E3A8A;'>🏢 Portal Documente Contabile</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #4B5563;'>Autentificare securizată pentru societăți și cabinetul de contabilitate</p>", unsafe_allow_html=True)
        st.markdown("---")
        
        with st.form("login_form"):
            username = st.text_input("Utilizator / CUI Societate", placeholder="ex: RO12345678 sau admin")
            pass_val = st.text_input("Parolă de Acces", type="password")
            submit = st.form_submit_button("🔑 Conectare", use_container_width=True)
            
            if submit:
                clean_user = username.strip()
                user_record = users.get(clean_user, {})
                expected_pass = user_record.get("user_key", user_record.get("password", ""))
                if clean_user in users and expected_pass == pass_val:
                    st.session_state.logged_in = True
                    st.session_state.user_info = {
                        "username": clean_user,
                        "role": users[clean_user]["role"],
                        "name": users[clean_user]["name"],
                        "cui": users[clean_user].get("cui", clean_user)
                    }
                    st.success("Autentificare reușită!")
                    st.rerun()
                else:
                    st.error("Utilizator sau parolă incorectă!")
                    
        st.info("""
        💡 **Conturi demo de test:**
        - **Client Demo 1**: `RO12345678` / parolă: `client_demo_1` (Alpha Tech SRL)
        - **Client Demo 2**: `RO98765432` / parolă: `client_demo_2` (Beta Construct SRL)
        - **Contabil (Admin)**: `admin` / parolă: `admin_demo` (Cabinet Contabilitate)
        """)
    st.stop()

# ------------------------------------------------------------------------------
# APLICAȚIA PRINCIPALĂ (DUPĂ LOGARE)
# ------------------------------------------------------------------------------
user = st.session_state.user_info
is_admin = (user["role"] == "admin")

# Bară Laterală Header / Logout
st.sidebar.markdown(f"### 👋 Salut, {user['name']}")
if is_admin:
    st.sidebar.markdown("🛡️ **Rol: Administrator / Contabil**")
else:
    st.sidebar.markdown(f"🏢 **CUI: {user['cui']}**")

if st.sidebar.button("🚪 Deconectare", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.user_info = None
    st.rerun()

st.sidebar.markdown("---")

# Selectare Societate
if is_admin:
    st.sidebar.markdown("### 🔍 Selectare Societate")
    client_options = {u["name"]: u for username, u in users.items() if u["role"] == "client"}
    selected_company_name = st.sidebar.selectbox("Alege Firma din Portofoliu:", list(client_options.keys()))
    current_company_name = selected_company_name
else:
    # Clientul vede DOAR propria firmă
    current_company_name = user["name"]
    st.sidebar.markdown(f"**Societate curentă:**\n`{current_company_name}`")

# Selectare Perioadă Contabilă (An & Lună)
st.sidebar.markdown("### 📅 Perioada Contabilă")
current_year = datetime.now().year
years = [current_year, current_year - 1, current_year + 1]
selected_year = st.sidebar.selectbox("Anul:", years, index=0)

months = [
    (1, "01 - Ianuarie"), (2, "02 - Februarie"), (3, "03 - Martie"),
    (4, "04 - Aprilie"), (5, "05 - Mai"), (6, "06 - Iunie"),
    (7, "07 - Iulie"), (8, "08 - August"), (9, "09 - Septembrie"),
    (10, "10 - Octombrie"), (11, "11 - Noiembrie"), (12, "12 - Decembrie")
]
current_month_num = datetime.now().month
selected_month_num = st.sidebar.selectbox(
    "Luna:",
    [m[0] for m in months],
    format_func=lambda x: [m[1] for m in months if m[0] == x][0],
    index=current_month_num - 1
)

month_label = [m[1] for m in months if m[0] == selected_month_num][0]

# Directorul curent pentru firma și luna aleasă
current_folder = get_company_month_dir(current_company_name, selected_year, selected_month_num)
metadata = load_metadata(current_folder)

# ------------------------------------------------------------------------------
# ECRAN PRINCIPAL
# ------------------------------------------------------------------------------
st.title(f"📁 Dosar Contabil: {current_company_name}")
st.subheader(f"Perioada: {month_label} {selected_year}")

# Tab-uri principale
tab_files, tab_upload, tab_camera, tab_dashboard = st.tabs([
    "📑 Documente în Folder", 
    "📤 Încărcare Fișiere (PDF, Excel, Poze)", 
    "📸 Pozează Document pe Loc",
    "📊 Tablou de Bord (Monitorizare)"
])

# ------------------------------------------------------------------------------
# TAB 1: Lista Documentelor din Folderul Unic
# ------------------------------------------------------------------------------
with tab_files:
    st.markdown(f"#### 📂 Conținut Folder: `{current_company_name} / {selected_year} / {month_label}`")
    
    all_files = [f for f in os.listdir(current_folder) if not f.startswith("_")]
    
    if not all_files:
        st.info("ℹ️ Nu există documente încărcate pentru această lună. Folosește tab-urile de încărcare pentru a adăuga documente.")
    else:
        st.markdown(f"**Total documente:** {len(all_files)}")
        
        # Tabel cu documente
        for idx, filename in enumerate(all_files):
            file_path = os.path.join(current_folder, filename)
            file_size = os.path.getsize(file_path)
            file_meta = metadata.get(filename, {})
            
            uploaded_by = file_meta.get("uploaded_by_role", "necunoscut")
            uploader_name = file_meta.get("uploader_name", "Utilizator")
            upload_time = file_meta.get("upload_time", "N/A")
            category = file_meta.get("category", "General")
            
            # Design etichetă
            if uploaded_by == "client":
                badge = "🟩 **[Încărcat de Client]**"
            elif uploaded_by == "admin":
                badge = "🟦 **[De la Contabilitate]**"
            else:
                badge = "⬜ **[Document]**"
                
            col_icon, col_details, col_actions = st.columns([1, 4, 2])
            
            with col_icon:
                ext = filename.split(".")[-1].lower()
                if ext in ["pdf"]:
                    st.markdown("🔴 **PDF**")
                elif ext in ["jpg", "jpeg", "png", "heic", "webp"]:
                    st.markdown("🖼️ **POZĂ**")
                elif ext in ["xlsx", "xls", "csv"]:
                    st.markdown("📊 **EXCEL**")
                else:
                    st.markdown("📄 **DOC**")
                    
            with col_details:
                st.markdown(f"**{filename}** ({format_file_size(file_size)})")
                st.caption(f"{badge} | Categorie: *{category}* | Adăugat de: **{uploader_name}** la {upload_time}")
                
            with col_actions:
                c1, c2 = st.columns(2)
                
                # Buton Descărcare
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
                c1.download_button(
                    label="⬇️ Descarcă",
                    data=file_bytes,
                    file_name=filename,
                    key=f"dl_{idx}_{filename}"
                )
                
                # Permisiune Ștergere
                can_delete = is_admin or (uploaded_by == "client")
                
                if can_delete:
                    if c2.button("🗑️ Șterge", key=f"del_{idx}_{filename}"):
                        try:
                            os.remove(file_path)
                            if filename in metadata:
                                del metadata[filename]
                                save_metadata(current_folder, metadata)
                            st.success(f"Fișierul `{filename}` a fost șters!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Eroare la ștergere: {e}")
                else:
                    c2.markdown("🔒 *Protejat*")
            st.divider()

# ------------------------------------------------------------------------------
# TAB 2: Încărcare Multi-Format + NOTIFICARE EMAIL
# ------------------------------------------------------------------------------
with tab_upload:
    st.markdown("### 📤 Încărcare Fișiere și Documente")
    
    category = st.selectbox(
        "Selectează Categoria Documentelor:",
        ["Facturi Intrați (Primite)", "Facturi Ieșiri (Emise)", "Extrase Bancare & Registru Casă", "Balanțe & Declarații Contabile", "Documente Salarii / Personal", "Alte Documente"],
        key="upload_cat"
    )
    
    uploaded_files = st.file_uploader(
        "Alege sau trage fișierele aici (PDF, JPEG, PNG, Excel, Word, ZIP etc.):",
        accept_multiple_files=True,
        type=None
    )
    
    if st.button("🚀 Salvează Fișierele în Folderul Lunii", use_container_width=True):
        if uploaded_files:
            saved_count = 0
            saved_filenames = []
            for uploaded_file in uploaded_files:
                original_name = uploaded_file.name
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_name = f"{timestamp}_{original_name}"
                dest_path = os.path.join(current_folder, save_name)
                
                with open(dest_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                    
                metadata[save_name] = {
                    "original_name": original_name,
                    "uploaded_by_username": user["username"],
                    "uploaded_by_role": user["role"],
                    "uploader_name": user["name"],
                    "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "category": category
                }
                saved_count += 1
                saved_filenames.append(original_name)
                
            save_metadata(current_folder, metadata)
            st.success(f"🎉 Am salvat cu succes {saved_count} document(e) în folderul `{current_company_name} / {month_label}`!")
            
            # Trimitere Notificare Email către Contabilitate
            if not is_admin:
                sent_ok, msg = send_email_notification(
                    company_name=current_company_name,
                    month_label=month_label,
                    year=selected_year,
                    file_list=saved_filenames,
                    uploader_name=user["name"],
                    category=category
                )
                if sent_ok:
                    st.info(f"📧 {msg}")
                else:
                    st.caption(f"ℹ️ Status notificare email: {msg}")
                    
            st.rerun()
        else:
            st.warning("Te rugăm să selectezi cel puțin un fișier înainte de a apăsa butonul.")

# ------------------------------------------------------------------------------
# TAB 3: Captură Foto Instantă + NOTIFICARE EMAIL
# ------------------------------------------------------------------------------
with tab_camera:
    st.markdown("### 📸 Pozează Documentul Fizic pe Loc")
    st.info("💡 Util de pe telefon/tabletă: Pozează direct bonurile de combustibil, chitanțele sau facturile pe hârtie.")
    
    photo_cat = st.selectbox(
        "Categorie pentru poza capturată:",
        ["Facturi Intrați (Primite)", "Bonuri & Chitanțe", "Extrase Bancare", "Alte Documente Fizice"],
        key="cam_cat"
    )
    
    camera_file = st.camera_input("Fă o poză clară documentului:")
    
    if camera_file is not None:
        st.image(camera_file, caption="Aperçu poză capturată", use_column_width=True)
        
        doc_label = st.text_input("Nume/Descriere scurtă document (ex: Bon_Benzina_OMV):", value="Bon_Fizic")
        
        if st.button("💾 Trimite Poza în Contabilitate", use_container_width=True):
            clean_label = "".join([c for c in doc_label if c.isalnum() or c in ('_', '-')]).strip()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_name = f"{timestamp}_{clean_label}.jpg"
            dest_path = os.path.join(current_folder, save_name)
            
            image = Image.open(camera_file)
            image.save(dest_path, "JPEG", quality=85)
            
            metadata[save_name] = {
                "original_name": f"{clean_label}.jpg",
                "uploaded_by_username": user["username"],
                "uploaded_by_role": user["role"],
                "uploader_name": user["name"],
                "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "category": photo_cat
            }
            save_metadata(current_folder, metadata)
            st.success(f"✅ Poza `{save_name}` a fost transmisă cu succes în folderul lunii!")
            
            # Trimitere Notificare Email către Contabilitate
            if not is_admin:
                sent_ok, msg = send_email_notification(
                    company_name=current_company_name,
                    month_label=month_label,
                    year=selected_year,
                    file_list=[f"{clean_label}.jpg"],
                    uploader_name=user["name"],
                    category=photo_cat
                )
                if sent_ok:
                    st.info(f"📧 {msg}")
                else:
                    st.caption(f"ℹ️ Status notificare email: {msg}")
                    
            st.rerun()

# ------------------------------------------------------------------------------
# TAB 4: Tablou de Bord & Monitorizare Predare Documente
# ------------------------------------------------------------------------------
with tab_dashboard:
    st.markdown(f"### 📊 Tablou de Bord Predare Documente - {month_label} {selected_year}")
    
    client_users = [u for username, u in users.items() if u["role"] == "client"]
    
    stats_data = []
    total_files_all = 0
    completed_companies = 0
    
    for c in client_users:
        c_name = c["name"]
        c_folder = get_company_month_dir(c_name, selected_year, selected_month_num)
        c_files = [f for f in os.listdir(c_folder) if not f.startswith("_")]
        c_count = len(c_files)
        total_files_all += c_count
        
        status = "🟢 Predat" if c_count > 0 else "🔴 Neîncărcat"
        if c_count > 0:
            completed_companies += 1
            
        stats_data.append({
            "Societate": c_name,
            "CUI": c["cui"],
            "Status": status,
            "Număr Documente": c_count
        })
        
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Firme în Portofoliu", len(client_users))
    c2.metric("Firme cu Documente Predate", completed_companies)
    c3.metric("Total Documente Colectate", total_files_all)
    
    st.markdown("---")
    st.markdown("#### Status Colectare pe Firme")
    
    for s in stats_data:
        col_name, col_status, col_count = st.columns([3, 2, 2])
        col_name.markdown(f"**{s['Societate']}** (`{s['CUI']}`)")
        col_status.markdown(s["Status"])
        col_count.markdown(f"📄 **{s['Număr Documente']}** documente")

# ------------------------------------------------------------------------------
# MENIU ADMINISTRARE: FIRME NOI & CONFIGURARE EMAIL
# ------------------------------------------------------------------------------
if is_admin:
    st.markdown("---")
    
    col_admin1, col_admin2 = st.columns(2)
    
    with col_admin1:
        with st.expander("➕ Adăugare Societate Nouă în Portofoliu"):
            with st.form("add_company_form"):
                new_cui = st.text_input("CUI Societate Nouă:", placeholder="ex: RO88899911")
                new_name = st.text_input("Denumire Completă Firmă:", placeholder="ex: Delta Services SRL")
                new_pass = st.text_input("Parolă Acces Client:", type="password")
                add_sub = st.form_submit_button("Adaugă Client Nou")
                
                if add_sub:
                    if new_cui and new_name and new_pass:
                        clean_cui = new_cui.strip()
                        if clean_cui in users:
                            st.error("Există deja un utilizator cu acest CUI!")
                        else:
                            users[clean_cui] = {
                                "user_key": new_pass.strip(),
                                "role": "client",
                                "name": new_name.strip(),
                                "cui": clean_cui
                            }
                            save_users(users)
                            st.success(f"Societatea **{new_name}** a fost adăugată cu succes!")
                            st.rerun()
                    else:
                        st.warning("Toate câmpurile sunt obligatorii.")

    with col_admin2:
        with st.expander("⚙️ Configurare Notificări Email (SMTP)"):
            current_cfg = load_email_config()
            
            with st.form("email_cfg_form"):
                cfg_enabled = st.checkbox("Activează notificările pe email", value=current_cfg.get("enabled", True))
                cfg_admin_email = st.text_input("Email Destinatar (Contabil / Admin):", value=current_cfg.get("admin_email", ""))
                cfg_sender_email = st.text_input("Email Expeditor (SMTP):", value=current_cfg.get("sender_email", ""))
                cfg_sender_key = st.text_input("Parolă / Cheie Aplicație SMTP:", value=current_cfg.get("sender_key", ""), type="password")
                
                c_smtp, c_port = st.columns(2)
                cfg_smtp_server = c_smtp.text_input("Server SMTP:", value=current_cfg.get("smtp_server", "smtp.example.com"))
                cfg_smtp_port = c_port.number_input("Port SMTP:", value=int(current_cfg.get("smtp_port", 587)))
                
                save_cfg_btn = st.form_submit_button("💾 Salvează Setările Email")
                
                if save_cfg_btn:
                    new_cfg = {
                        "enabled": cfg_enabled,
                        "admin_email": cfg_admin_email.strip(),
                        "sender_email": cfg_sender_email.strip(),
                        "sender_key": cfg_sender_key.strip(),
                        "smtp_server": cfg_smtp_server.strip(),
                        "smtp_port": int(cfg_smtp_port)
                    }
                    save_email_config(new_cfg)
                    st.success("Setările de email au fost salvate cu succes!")
                    st.rerun()
            
            if st.button("🧪 Trimite Email de Test"):
                ok, msg = send_email_notification(
                    company_name="FIRMA DEMO TEST",
                    month_label="Noiembrie",
                    year=2026,
                    file_list=["Factura_Test.pdf"],
                    uploader_name="Sistem Test",
                    category="Test Notificare"
                )
                if ok:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")
