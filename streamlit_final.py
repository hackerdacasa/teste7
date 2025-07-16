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

# Configuração
DOWNLOADS_DIR = "downloads"
DB_PATH = "downloads.db"

if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

# FFmpeg
@st.cache_resource
def get_ffmpeg_path():
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
    
    # Verificar colunas
    cursor.execute("PRAGMA table_info(downloads)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'format_type' not in columns:
        cursor.execute('ALTER TABLE downloads ADD COLUMN format_type TEXT DEFAULT "video"')
    
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

def update_download(download_id, **kwargs):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    for key, value in kwargs.items():
        if value is not None:
            updates.append(f"{key} = ?")
            params.append(value)
    
    if updates:
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
    
    if any(pattern in url_lower for pattern in ['youtube.com', 'youtu.be']):
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
        update_download(download_id, status='downloading')
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT url, platform FROM downloads WHERE id = ?", (download_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return
        
        url, platform = result
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    if 'total_bytes' in d:
                        progress = int((d.get('downloaded_bytes', 0) / d['total_bytes']) * 100)
                    elif 'total_bytes_estimate' in d:
                        progress = int((d.get('downloaded_bytes', 0) / d['total_bytes_estimate']) * 100)
                    else:
                        progress = 0
                    
                    update_download(download_id, progress=min(progress, 99))
                except:
                    pass
        
        # Configuração
        base_opts = {
            'outtmpl': os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'progress_hooks': [progress_hook],
        }
        
        if FFMPEG_PATH:
            base_opts['ffmpeg_location'] = FFMPEG_PATH
        
        if format_type == 'audio':
            ydl_opts = {
                **base_opts,
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'keepvideo': False,
            }
        else:
            if platform == 'instagram':
                ydl_opts = {
                    **base_opts,
                    'format': 'best',
                }
            else:
                ydl_opts = {
                    **base_opts,
                    'format': 'best[ext=mp4][height<=720]/best[ext=mp4]/best',
                }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Video')
            
            update_download(download_id, title=title)
            
            ydl.download([url])
            
            # Encontrar arquivo baixado
            filename = None
            download_files = os.listdir(DOWNLOADS_DIR)
            
            # Procurar por arquivo MP3 primeiro (se for conversão de áudio)
            if format_type == 'audio':
                for file in download_files:
                    if file.endswith('.mp3') and title[:30] in file:
                        filename = file
                        break
            
            # Se não encontrou MP3 ou não é áudio, procurar por qualquer arquivo
            if not filename:
                for file in download_files:
                    if title[:30] in file:
                        filename = file
                        break
            
            # Se ainda não encontrou, procurar por arquivo mais recente
            if not filename and download_files:
                # Ordenar por data de modificação (mais recente primeiro)
                files_with_time = [(f, os.path.getmtime(os.path.join(DOWNLOADS_DIR, f))) for f in download_files]
                files_with_time.sort(key=lambda x: x[1], reverse=True)
                
                # Pegar o mais recente que não seja .part ou .tmp
                for file, _ in files_with_time:
                    if not file.endswith(('.part', '.tmp')):
                        filename = file
                        break
            
            if filename:
                file_path = os.path.join(DOWNLOADS_DIR, filename)
                if os.path.exists(file_path):
                    file_size = format_file_size(os.path.getsize(file_path))
                    update_download(download_id, status='completed', progress=100, filename=filename, file_size=file_size)
                else:
                    update_download(download_id, status='completed', progress=100)
            else:
                update_download(download_id, status='completed', progress=100)
                
    except Exception as e:
        update_download(download_id, status='failed', error_message=str(e))

# Inicializar
init_db()

# Interface
st.title("🎬 Video Downloader")
st.markdown("Baixe vídeos do YouTube e Instagram em MP4 ou MP3")

# Status FFmpeg
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
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM downloads WHERE url = ? AND status != 'failed'", (url,))
                existing = cursor.fetchone()
                conn.close()
                
                if existing:
                    st.warning("URL já foi baixada")
                else:
                    download_id = add_download(url, platform, format_type)
                    
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
        # Parsing robusto
        download_data = {
            'id': download[0],
            'url': download[1],
            'title': download[2],
            'platform': download[3],
            'format_type': download[4] if len(download) > 4 else 'video',
            'status': download[5] if len(download) > 5 else download[4],
            'progress': download[6] if len(download) > 6 else download[5],
            'filename': download[7] if len(download) > 7 else download[6],
            'file_size': download[8] if len(download) > 8 else download[7],
            'error_message': download[9] if len(download) > 9 else download[8],
            'created_at': download[10] if len(download) > 10 else download[9]
        }
        
        # Ajustar se format_type não existe
        if len(download) <= 4:
            download_data['format_type'] = 'video'
            download_data['status'] = download[4]
            download_data['progress'] = download[5]
            download_data['filename'] = download[6]
            download_data['file_size'] = download[7]
            download_data['error_message'] = download[8]
            download_data['created_at'] = download[9]
        
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.markdown(f"**{download_data['title'] or 'Carregando...'}**")
                platform_icon = "🔴" if download_data['platform'] == "youtube" else "📷"
                format_icon = "🎬" if download_data['format_type'] == "video" else "🎵"
                st.markdown(f"{platform_icon} {download_data['platform'].title()} • {format_icon} {download_data['format_type'].title()}")
                st.markdown(f"🕐 {download_data['created_at']}")
                if download_data['file_size']:
                    st.markdown(f"📁 {download_data['file_size']}")
            
            with col2:
                if download_data['status'] == "completed":
                    st.success("✅ Concluído")
                elif download_data['status'] == "downloading":
                    st.info("⏳ Baixando...")
                    if download_data['progress']:
                        st.progress(download_data['progress'] / 100)
                        st.markdown(f"{download_data['progress']}%")
                elif download_data['status'] == "pending":
                    st.warning("⏳ Aguardando...")
                elif download_data['status'] == "failed":
                    st.error("❌ Falhou")
                    if download_data['error_message']:
                        st.error(f"Erro: {download_data['error_message']}")
            
            with col3:
                if download_data['status'] == "completed" and download_data['filename']:
                    file_path = os.path.join(DOWNLOADS_DIR, download_data['filename'])
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as file:
                            st.download_button(
                                label="📥 Baixar",
                                data=file.read(),
                                file_name=download_data['filename'],
                                key=f"download_{download_data['id']}"
                            )
                
                if st.button("🗑️ Remover", key=f"delete_{download_data['id']}"):
                    delete_download(download_data['id'])
                    st.rerun()
            
            st.divider()
    
    # Auto-refresh
    if any(download_data['status'] in ['downloading', 'pending'] for download in downloads):
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