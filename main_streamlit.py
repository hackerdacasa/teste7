import streamlit as st
import yt_dlp
import os
import re
import threading
import time
from datetime import datetime
from urllib.parse import urlparse
import sqlite3
import shutil

# Configuração da página
st.set_page_config(
    page_title="Video Downloader",
    page_icon="🎬",
    layout="wide"
)

# Configuração de diretórios
DOWNLOADS_DIR = "downloads"
DB_PATH = "downloads.db"

# Criar diretório se não existir
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

# Encontrar FFmpeg
@st.cache_resource
def get_ffmpeg_path():
    """Encontra e retorna o caminho do FFmpeg"""
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        return os.path.dirname(ffmpeg_path)
    return None

FFMPEG_PATH = get_ffmpeg_path()

# Banco de dados
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            title TEXT,
            platform TEXT,
            format_type TEXT DEFAULT 'video',
            status TEXT DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            filename TEXT,
            file_size TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def add_download(url, platform, format_type):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO downloads (url, platform, format_type)
        VALUES (?, ?, ?)
    ''', (url, platform, format_type))
    download_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return download_id

def get_downloads():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM downloads ORDER BY created_at DESC')
    downloads = cursor.fetchall()
    conn.close()
    return downloads

def update_download_status(download_id, status, progress=None, title=None, filename=None, file_size=None, error_message=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    updates.append("status = ?")
    params.append(status)
    
    if progress is not None:
        updates.append("progress = ?")
        params.append(progress)
    
    if title is not None:
        updates.append("title = ?")
        params.append(title)
    
    if filename is not None:
        updates.append("filename = ?")
        params.append(filename)
    
    if file_size is not None:
        updates.append("file_size = ?")
        params.append(file_size)
    
    if error_message is not None:
        updates.append("error_message = ?")
        params.append(error_message)
    
    params.append(download_id)
    
    query = f"UPDATE downloads SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def delete_download(download_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT filename FROM downloads WHERE id = ?", (download_id,))
    result = cursor.fetchone()
    
    if result and result[0]:
        file_path = os.path.join(DOWNLOADS_DIR, result[0])
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
    
    cursor.execute("DELETE FROM downloads WHERE id = ?", (download_id,))
    conn.commit()
    conn.close()

# Validação
def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def detect_platform(url):
    url_lower = url.lower()
    
    if any(pattern in url_lower for pattern in ['youtube.com', 'youtu.be', 'youtube-nocookie.com']):
        return 'youtube'
    elif any(pattern in url_lower for pattern in ['instagram.com', 'instagr.am']):
        return 'instagram'
    
    return None

def format_file_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

# Download
def download_video(download_id, format_type):
    try:
        update_download_status(download_id, 'downloading')
        
        # Buscar URL
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT url, platform FROM downloads WHERE id = ?", (download_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return
        
        url, platform = result
        
        # Progress hook
        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    if 'total_bytes' in d:
                        progress = int((d.get('downloaded_bytes', 0) / d['total_bytes']) * 100)
                    elif 'total_bytes_estimate' in d:
                        progress = int((d.get('downloaded_bytes', 0) / d['total_bytes_estimate']) * 100)
                    else:
                        progress = 0
                    
                    update_download_status(download_id, 'downloading', progress=min(progress, 99))
                except:
                    pass
        
        # Configuração base
        base_opts = {
            'outtmpl': os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'progress_hooks': [progress_hook],
        }
        
        # Adicionar FFmpeg se disponível
        if FFMPEG_PATH:
            base_opts['ffmpeg_location'] = FFMPEG_PATH
        
        # Configuração específica por formato
        if format_type == 'audio':
            ydl_opts = {
                **base_opts,
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
        else:
            # Configuração por plataforma
            if platform == 'instagram':
                ydl_opts = {
                    **base_opts,
                    'format': 'best',
                }
            else:  # YouTube
                ydl_opts = {
                    **base_opts,
                    'format': 'best[ext=mp4][height<=720]/best[ext=mp4]/best[height<=720]/best',
                }
        
        # Executar download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extrair info
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Video')
            
            update_download_status(download_id, 'downloading', title=title)
            
            # Download
            ydl.download([url])
            
            # Encontrar arquivo
            filename = None
            for file in os.listdir(DOWNLOADS_DIR):
                if file.startswith(title[:30]):
                    filename = file
                    break
            
            if filename:
                file_path = os.path.join(DOWNLOADS_DIR, filename)
                if os.path.exists(file_path):
                    file_size = format_file_size(os.path.getsize(file_path))
                    update_download_status(download_id, 'completed', progress=100, filename=filename, file_size=file_size)
                else:
                    update_download_status(download_id, 'completed', progress=100)
            else:
                update_download_status(download_id, 'completed', progress=100)
                
    except Exception as e:
        update_download_status(download_id, 'failed', error_message=str(e))

# Inicializar
init_db()

# CSS personalizado
st.markdown("""
<style>
    .stButton > button {
        width: 100%;
    }
    .download-card {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 10px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Interface
st.title("🎬 Video Downloader")
st.markdown("Baixe vídeos do YouTube e Instagram em MP4 ou MP3")

# Mostrar status do FFmpeg
if FFMPEG_PATH:
    st.success(f"✅ FFmpeg encontrado: {FFMPEG_PATH}")
else:
    st.warning("⚠️ FFmpeg não encontrado - conversão de áudio pode falhar")

# Sidebar
with st.sidebar:
    st.header("📥 Novo Download")
    
    url = st.text_input("URL do vídeo:", placeholder="Cole a URL aqui...")
    
    format_type = st.radio(
        "Formato:",
        ["video", "audio"],
        format_func=lambda x: "🎬 Vídeo (MP4)" if x == "video" else "🎵 Áudio (MP3)"
    )
    
    if st.button("🚀 Baixar"):
        if not url:
            st.error("Insira uma URL válida")
        elif not is_valid_url(url):
            st.error("URL inválida")
        else:
            platform = detect_platform(url)
            if not platform:
                st.error("Plataforma não suportada")
            else:
                # Verificar duplicata
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM downloads WHERE url = ? AND status != 'failed'", (url,))
                existing = cursor.fetchone()
                conn.close()
                
                if existing:
                    st.warning("URL já foi baixada")
                else:
                    download_id = add_download(url, platform, format_type)
                    
                    # Iniciar download
                    thread = threading.Thread(target=download_video, args=(download_id, format_type))
                    thread.daemon = True
                    thread.start()
                    
                    st.success("Download iniciado!")
                    st.rerun()

# Lista de downloads
st.header("📋 Downloads")

downloads = get_downloads()

if downloads:
    for download in downloads:
        download_id, url, title, platform, format_type, status, progress, filename, file_size, error_message, created_at = download
        
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.markdown(f"**{title or 'Carregando...'}**")
                platform_icon = "🔴" if platform == "youtube" else "📷"
                format_icon = "🎬" if format_type == "video" else "🎵"
                st.markdown(f"{platform_icon} {platform.title()} • {format_icon} {format_type.title()}")
                st.markdown(f"🕐 {created_at}")
                if file_size:
                    st.markdown(f"📁 {file_size}")
            
            with col2:
                if status == "completed":
                    st.success("✅ Concluído")
                elif status == "downloading":
                    st.info("⏳ Baixando...")
                    if progress:
                        st.progress(progress / 100)
                        st.markdown(f"{progress}%")
                elif status == "pending":
                    st.warning("⏳ Aguardando...")
                elif status == "failed":
                    st.error("❌ Falhou")
                    if error_message:
                        st.error(f"Erro: {error_message}")
            
            with col3:
                if status == "completed" and filename:
                    file_path = os.path.join(DOWNLOADS_DIR, filename)
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as file:
                            st.download_button(
                                label="📥 Baixar",
                                data=file.read(),
                                file_name=filename,
                                key=f"download_{download_id}"
                            )
                
                if st.button("🗑️ Remover", key=f"delete_{download_id}"):
                    delete_download(download_id)
                    st.rerun()
            
            st.divider()
    
    # Auto-refresh para downloads ativos
    if any(download[5] in ['downloading', 'pending'] for download in downloads):
        time.sleep(2)
        st.rerun()
else:
    st.info("Nenhum download encontrado")

# Informações
with st.expander("ℹ️ Informações"):
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🔴 YouTube**")
        st.markdown("• youtube.com")
        st.markdown("• youtu.be")
    
    with col2:
        st.markdown("**📷 Instagram**")
        st.markdown("• instagram.com")
        st.markdown("• instagr.am")

st.markdown("---")
st.markdown("🚀 Powered by yt-dlp")