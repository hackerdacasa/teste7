#!/usr/bin/env python3
"""
Correção para o problema do MP3 no Streamlit
"""
import streamlit as st
import yt_dlp
import os
import shutil
import sqlite3
import threading
import time
from datetime import datetime

# Configuração
st.set_page_config(page_title="Video Downloader - MP3 Fix", page_icon="🎬", layout="wide")

DOWNLOADS_DIR = "downloads"
DB_PATH = "downloads.db"

if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

# FFmpeg
FFMPEG_PATH = os.path.dirname(shutil.which('ffmpeg')) if shutil.which('ffmpeg') else None

# Banco
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
    cursor.execute('INSERT INTO downloads (url, platform, format_type) VALUES (?, ?, ?)', (url, platform, format_type))
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
    from urllib.parse import urlparse
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

# Download corrigido
def download_video_fixed(download_id, format_type):
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
                    
                    update_download(download_id, progress=min(progress, 99))
                except:
                    pass
        
        # Configuração fixa
        if format_type == 'audio':
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'progress_hooks': [progress_hook],
                'noplaylist': True,
                'keepvideo': False,
            }
        else:
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'outtmpl': os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s'),
                'progress_hooks': [progress_hook],
                'noplaylist': True,
            }
        
        # Adicionar FFmpeg se disponível
        if FFMPEG_PATH:
            ydl_opts['ffmpeg_location'] = FFMPEG_PATH
        
        # Executar download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extrair info
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Video')
            
            # Armazenar arquivos antes do download
            files_before = set(os.listdir(DOWNLOADS_DIR))
            
            update_download(download_id, title=title)
            
            # Fazer download
            ydl.download([url])
            
            # Encontrar novos arquivos
            files_after = set(os.listdir(DOWNLOADS_DIR))
            new_files = files_after - files_before
            
            filename = None
            
            # Para áudio, procurar especificamente MP3
            if format_type == 'audio':
                for file in new_files:
                    if file.endswith('.mp3'):
                        filename = file
                        break
            
            # Se não encontrou ou não é áudio, pegar qualquer arquivo novo
            if not filename and new_files:
                filename = list(new_files)[0]
            
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
st.title("🎬 Video Downloader - MP3 Corrigido")

# Status do sistema
col1, col2 = st.columns(2)
with col1:
    if FFMPEG_PATH:
        st.success(f"✅ FFmpeg: {FFMPEG_PATH}")
    else:
        st.error("❌ FFmpeg não encontrado")

with col2:
    downloads_count = len(get_downloads())
    st.info(f"📊 Total de downloads: {downloads_count}")

# Formulário
with st.sidebar:
    st.header("📥 Novo Download")
    
    url = st.text_input("URL:", placeholder="Cole a URL aqui...")
    
    format_type = st.radio(
        "Formato:",
        ["video", "audio"],
        format_func=lambda x: "🎬 Vídeo (MP4)" if x == "video" else "🎵 Áudio (MP3)"
    )
    
    if st.button("🚀 Baixar"):
        if not url:
            st.error("Insira uma URL")
        elif not is_valid_url(url):
            st.error("URL inválida")
        else:
            platform = detect_platform(url)
            if not platform:
                st.error("Plataforma não suportada")
            else:
                download_id = add_download(url, platform, format_type)
                
                thread = threading.Thread(target=download_video_fixed, args=(download_id, format_type))
                thread.daemon = True
                thread.start()
                
                st.success("Download iniciado!")
                st.rerun()

# Lista de downloads
st.header("📋 Downloads")

downloads = get_downloads()

if downloads:
    for download in downloads:
        # Parsing seguro
        download_data = {}
        try:
            download_data['id'] = download[0]
            download_data['url'] = download[1]
            download_data['title'] = download[2]
            download_data['platform'] = download[3]
            download_data['format_type'] = download[4] if len(download) > 4 else 'video'
            download_data['status'] = download[5] if len(download) > 5 else 'pending'
            download_data['progress'] = download[6] if len(download) > 6 else 0
            download_data['filename'] = download[7] if len(download) > 7 else None
            download_data['file_size'] = download[8] if len(download) > 8 else None
            download_data['error_message'] = download[9] if len(download) > 9 else None
            download_data['created_at'] = download[10] if len(download) > 10 else None
        except:
            continue
        
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.markdown(f"**{download_data['title'] or 'Carregando...'}**")
                platform_icon = "🔴" if download_data['platform'] == "youtube" else "📷"
                format_icon = "🎬" if download_data['format_type'] == "video" else "🎵"
                st.markdown(f"{platform_icon} {download_data['platform'].title()} • {format_icon} {download_data['format_type'].title()}")
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
    if any(d[5] in ['downloading', 'pending'] for d in downloads if len(d) > 5):
        time.sleep(2)
        st.rerun()
else:
    st.info("Nenhum download encontrado")

# Informações
with st.expander("ℹ️ Informações"):
    st.markdown("**Plataformas suportadas:**")
    st.markdown("• 🔴 YouTube (youtube.com, youtu.be)")
    st.markdown("• 📷 Instagram (instagram.com)")
    st.markdown("**Formatos:**")
    st.markdown("• 🎬 Vídeo: MP4 (melhor qualidade disponível)")
    st.markdown("• 🎵 Áudio: MP3 (192kbps)")

st.markdown("---")
st.markdown("🔧 Versão corrigida com FFmpeg otimizado")