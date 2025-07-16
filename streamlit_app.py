import streamlit as st
import yt_dlp
import os
import re
import threading
import time
from datetime import datetime
from urllib.parse import urlparse
import sqlite3
import json
import shutil
import subprocess

# Configuração da página
st.set_page_config(
    page_title="Video Downloader",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuração de diretórios
DOWNLOADS_DIR = os.path.join(os.getcwd(), 'downloads')
DB_PATH = os.path.join(os.getcwd(), 'downloads.db')

# Criar diretório de downloads se não existir
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

# Encontrar FFmpeg
def find_ffmpeg():
    """Encontra o caminho do FFmpeg no sistema"""
    ffmpeg_path = shutil.which('ffmpeg')
    ffprobe_path = shutil.which('ffprobe')
    
    if ffmpeg_path and ffprobe_path:
        return os.path.dirname(ffmpeg_path)
    
    # Caminhos comuns do FFmpeg
    common_paths = [
        '/usr/bin',
        '/usr/local/bin',
        '/opt/homebrew/bin',
        '/home/runner/.nix-profile/bin'
    ]
    
    for path in common_paths:
        if os.path.exists(os.path.join(path, 'ffmpeg')) and os.path.exists(os.path.join(path, 'ffprobe')):
            return path
    
    return None

FFMPEG_PATH = find_ffmpeg()

# Inicializar banco de dados
def init_database():
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')
    
    # Verificar se a coluna completed_at existe, se não, adicionar
    cursor.execute("PRAGMA table_info(downloads)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'completed_at' not in columns:
        cursor.execute('ALTER TABLE downloads ADD COLUMN completed_at TIMESTAMP')
    
    if 'format_type' not in columns:
        cursor.execute('ALTER TABLE downloads ADD COLUMN format_type TEXT DEFAULT "video"')
    
    conn.commit()
    conn.close()

# Funções de banco de dados
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
    cursor.execute('''
        SELECT * FROM downloads 
        ORDER BY created_at DESC
    ''')
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
    
    if status == 'completed':
        updates.append("completed_at = CURRENT_TIMESTAMP")
    
    params.append(download_id)
    
    query = f"UPDATE downloads SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def delete_download(download_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Buscar informações do download
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

# Validação de URL
def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def detect_platform(url):
    url_lower = url.lower()
    
    # YouTube patterns
    youtube_patterns = [
        r'youtube\.com',
        r'youtu\.be',
        r'youtube-nocookie\.com'
    ]
    
    # Instagram patterns
    instagram_patterns = [
        r'instagram\.com',
        r'instagr\.am'
    ]
    
    for pattern in youtube_patterns:
        if re.search(pattern, url_lower):
            return 'youtube'
    
    for pattern in instagram_patterns:
        if re.search(pattern, url_lower):
            return 'instagram'
    
    return None

# Formatação de tamanho de arquivo
def format_file_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

# Função de download
def download_video(download_id, format_type):
    try:
        update_download_status(download_id, 'downloading')
        
        # Buscar informações do download
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM downloads WHERE id = ?", (download_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return
        
        url = result[0]
        
        # Configurar yt-dlp
        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    if 'total_bytes' in d:
                        downloaded = d.get('downloaded_bytes', 0)
                        total = d['total_bytes']
                        progress = int((downloaded / total) * 100)
                    elif 'total_bytes_estimate' in d:
                        downloaded = d.get('downloaded_bytes', 0)
                        total = d['total_bytes_estimate']
                        progress = int((downloaded / total) * 100)
                    else:
                        progress = 0
                    
                    update_download_status(download_id, 'downloading', progress=min(progress, 99))
                except:
                    pass
        
        # Configuração básica do yt-dlp
        base_opts = {
            'outtmpl': os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'progress_hooks': [progress_hook],
        }
        
        # Adicionar caminho do FFmpeg se disponível
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
            }
        else:
            ydl_opts = {
                **base_opts,
                'format': 'best[ext=mp4][height<=720]/best[ext=mp4]/best[height<=720]/best',
            }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extrair informações
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown Title')
            
            update_download_status(download_id, 'downloading', title=title)
            
            # Fazer download
            ydl.download([url])
            
            # Procurar arquivo baixado
            filename = None
            for file in os.listdir(DOWNLOADS_DIR):
                if file.startswith(title[:50]):
                    filename = file
                    break
            
            if filename:
                file_path = os.path.join(DOWNLOADS_DIR, filename)
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    file_size_str = format_file_size(file_size)
                    
                    update_download_status(
                        download_id, 
                        'completed', 
                        progress=100,
                        filename=filename,
                        file_size=file_size_str
                    )
                else:
                    update_download_status(download_id, 'completed', progress=100)
            else:
                update_download_status(download_id, 'completed', progress=100)
                
    except Exception as e:
        update_download_status(download_id, 'failed', error_message=str(e))

# Inicializar banco
init_database()

# Interface Streamlit
st.title("🎬 Video Downloader")
st.markdown("Baixe vídeos do YouTube e Instagram em MP4 ou MP3")

# Sidebar para novo download
with st.sidebar:
    st.header("📥 Novo Download")
    
    # Input da URL
    url = st.text_input("URL do vídeo:", placeholder="Cole aqui a URL do YouTube ou Instagram...")
    
    # Seleção de formato
    format_type = st.radio(
        "Formato:",
        ["video", "audio"],
        format_func=lambda x: "🎬 Vídeo (MP4)" if x == "video" else "🎵 Áudio (MP3)"
    )
    
    # Botão de download
    if st.button("🚀 Iniciar Download", use_container_width=True):
        if not url:
            st.error("Por favor, insira uma URL válida.")
        elif not is_valid_url(url):
            st.error("URL inválida. Por favor, insira uma URL válida.")
        else:
            platform = detect_platform(url)
            if not platform:
                st.error("Plataforma não suportada. Apenas YouTube e Instagram são suportados.")
            else:
                # Verificar se URL já existe
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM downloads WHERE url = ? AND status != 'failed'", (url,))
                existing = cursor.fetchone()
                conn.close()
                
                if existing:
                    st.warning("Esta URL já foi baixada ou está em processo de download.")
                else:
                    download_id = add_download(url, platform, format_type)
                    
                    # Iniciar download em thread separada
                    thread = threading.Thread(target=download_video, args=(download_id, format_type))
                    thread.daemon = True
                    thread.start()
                    
                    st.success(f"Download de {'áudio' if format_type == 'audio' else 'vídeo'} iniciado!")
                    st.rerun()

# Área principal - Lista de downloads
st.header("📋 Histórico de Downloads")

downloads = get_downloads()

if downloads:
    for download in downloads:
        # Lidar com diferentes estruturas de banco
        if len(download) == 12:
            download_id, url, title, platform, format_type, status, progress, filename, file_size, error_message, created_at, completed_at = download
        elif len(download) == 11:
            download_id, url, title, platform, format_type, status, progress, filename, file_size, error_message, created_at = download
            completed_at = None
        else:
            # Estrutura mais antiga
            download_id, url, title, platform, status, progress, filename, file_size, error_message, created_at = download[:10]
            format_type = 'video'
            completed_at = None
        
        # Container para cada download
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                # Título e informações
                display_title = title if title else "Carregando título..."
                st.markdown(f"**{display_title}**")
                
                # Plataforma
                platform_icon = "🔴" if platform == "youtube" else "📷" if platform == "instagram" else "🌐"
                format_icon = "🎬" if format_type == "video" else "🎵"
                st.markdown(f"{platform_icon} {platform.title()} • {format_icon} {format_type.title()}")
                
                # Data
                st.markdown(f"🕐 {created_at}")
                
                # Tamanho do arquivo
                if file_size:
                    st.markdown(f"📁 {file_size}")
            
            with col2:
                # Status e progresso
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
                # Ações
                if status == "completed" and filename:
                    file_path = os.path.join(DOWNLOADS_DIR, filename)
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as file:
                            st.download_button(
                                label="📥 Baixar",
                                data=file.read(),
                                file_name=filename,
                                mime="application/octet-stream",
                                key=f"download_{download_id}"
                            )
                
                if st.button("🗑️ Remover", key=f"delete_{download_id}"):
                    delete_download(download_id)
                    st.rerun()
            
            st.divider()
    
    # Auto-refresh para downloads em progresso
    if any(download[4] in ['downloading', 'pending'] for download in downloads):
        time.sleep(2)
        st.rerun()
else:
    st.info("Nenhum download encontrado. Use o painel lateral para iniciar um novo download.")

# Informações sobre plataformas suportadas
with st.expander("ℹ️ Plataformas Suportadas"):
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🔴 YouTube**")
        st.markdown("• youtube.com")
        st.markdown("• youtu.be")
        st.markdown("• youtube-nocookie.com")
    
    with col2:
        st.markdown("**📷 Instagram**")
        st.markdown("• instagram.com")
        st.markdown("• instagr.am")

# Rodapé
st.markdown("---")
st.markdown("🚀 Powered by yt-dlp • Desenvolvido com Streamlit")