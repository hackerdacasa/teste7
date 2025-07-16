import streamlit as st
import yt_dlp
import os
import re
import threading
import time
from datetime import datetime
import sqlite3
import shutil
import subprocess
from pathlib import Path

# Configuração da página
st.set_page_config(
    page_title="🎵 Modern MP3 Converter",
    page_icon="🎵",
    layout="wide"
)

# CSS moderno
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
    
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    .main-title {
        font-family: 'Poppins', sans-serif;
        font-size: 3.5rem;
        font-weight: 700;
        text-align: center;
        background: linear-gradient(135deg, #ff6b6b, #4ecdc4, #45b7d1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 2rem;
    }
    
    .modern-card {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 2rem;
        margin: 1.5rem 0;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    .status-completed { background: #4CAF50; color: white; padding: 0.5rem 1rem; border-radius: 10px; }
    .status-failed { background: #f44336; color: white; padding: 0.5rem 1rem; border-radius: 10px; }
    .status-downloading { background: #2196F3; color: white; padding: 0.5rem 1rem; border-radius: 10px; }
    .status-pending { background: #FF9800; color: white; padding: 0.5rem 1rem; border-radius: 10px; }
    
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.75rem 2rem;
        font-family: 'Poppins', sans-serif;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# Configuração
DOWNLOADS_DIR = "downloads"
DB_PATH = "downloads.db"
UPLOADS_DIR = "uploads"

# Criar diretórios
for directory in [DOWNLOADS_DIR, UPLOADS_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# FFmpeg - Caminho fixo do Nix
FFMPEG_PATH = "/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffmpeg"
FFPROBE_PATH = "/nix/store/3zc5jbvqzrn8zmva4fx5p0nh4yy03wk4-ffmpeg-6.1.1-bin/bin/ffprobe"

# Verificar se FFmpeg existe
FFMPEG_AVAILABLE = os.path.exists(FFMPEG_PATH) and os.path.exists(FFPROBE_PATH)

# Banco de dados
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            title TEXT,
            platform TEXT,
            format_type TEXT DEFAULT 'audio',
            quality TEXT DEFAULT 'best',
            status TEXT DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            filename TEXT,
            file_size TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_local_file BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def add_download(url, platform, format_type, quality='best', is_local_file=False):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO downloads (url, platform, format_type, quality, is_local_file)
        VALUES (?, ?, ?, ?, ?)
    ''', (url, platform, format_type, quality, is_local_file))
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

def is_valid_url(url):
    return url.startswith('http')

def detect_platform(url):
    if 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube'
    return 'other'

def format_file_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    size_name = ["B", "KB", "MB", "GB", "TB"]
    i = int(size_bytes.bit_length() / 10)
    p = 1024 ** i
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

def convert_local_to_mp3(file_path, download_id):
    try:
        update_download(download_id, status='downloading', progress=10)
        
        file_name = os.path.basename(file_path)
        name_without_ext = os.path.splitext(file_name)[0]
        
        output_filename = f"{name_without_ext}.mp3"
        output_path = os.path.join(DOWNLOADS_DIR, output_filename)
        
        update_download(download_id, title=name_without_ext, filename=output_filename, progress=30)
        
        cmd = [
            FFMPEG_PATH, '-i', file_path,
            '-vn', '-acodec', 'libmp3lame',
            '-b:a', '320k', '-ar', '44100', '-ac', '2',
            '-y', output_path
        ]
        
        update_download(download_id, progress=50)
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            file_size = os.path.getsize(output_path)
            file_size_str = format_file_size(file_size)
            
            try:
                os.remove(file_path)
            except:
                pass
            
            update_download(download_id, status='completed', progress=100, file_size=file_size_str)
        else:
            update_download(download_id, status='failed', error_message=f"Erro FFmpeg: {result.stderr}")
    
    except Exception as e:
        update_download(download_id, status='failed', error_message=f"Erro: {str(e)}")

def download_youtube_video(download_id, url, format_type, quality):
    try:
        update_download(download_id, status='downloading', progress=5)
        
        # Configurar qualidade
        if quality == "4K (2160p)":
            format_selector = 'best[height<=2160]'
        elif quality == "1080p":
            format_selector = 'best[height<=1080]'
        elif quality == "720p":
            format_selector = 'best[height<=720]'
        elif quality == "480p":
            format_selector = 'best[height<=480]'
        else:
            format_selector = 'best'
        
        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s'),
            'ffmpeg_location': FFMPEG_PATH,
        }
        
        if format_type == 'audio':
            ydl_opts.update({
                'format': 'bestaudio',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
            })
        else:
            ydl_opts['format'] = format_selector
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    percent_str = d.get('_percent_str', '0%')
                    percent = int(float(percent_str.replace('%', '')))
                    update_download(download_id, progress=percent)
                except:
                    pass
            elif d['status'] == 'finished':
                filename = os.path.basename(d['filename'])
                file_size = format_file_size(os.path.getsize(d['filename']))
                update_download(download_id, filename=filename, file_size=file_size, progress=95)
        
        ydl_opts['progress_hooks'] = [progress_hook]
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Título não disponível')
            
            update_download(download_id, title=title, progress=10)
            
            ydl.download([url])
            
            update_download(download_id, status='completed', progress=100)
    
    except Exception as e:
        update_download(download_id, status='failed', error_message=str(e))

def main():
    init_db()
    
    st.markdown('<h1 class="main-title">🎵 Modern MP3 Converter</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 🎛️ Controles")
        
        # Status FFmpeg
        if FFMPEG_AVAILABLE:
            st.success("✅ FFmpeg Funcionando")
        else:
            st.error("❌ FFmpeg não encontrado")
        
        # Tipo de conversão
        conversion_type = st.radio(
            "Tipo:",
            ["📹 YouTube", "🎵 Arquivo Local"]
        )
        
        if conversion_type == "📹 YouTube":
            st.markdown("### 🔗 YouTube")
            
            # Formato
            format_type = st.selectbox(
                "Formato:",
                ["🎵 MP3", "📹 MP4"]
            )
            
            # Qualidade
            if "MP4" in format_type:
                quality = st.selectbox(
                    "Qualidade:",
                    ["Melhor", "4K (2160p)", "1080p", "720p", "480p"]
                )
            else:
                quality = "320kbps"
                st.info("🎵 Áudio: 320kbps")
            
            url = st.text_input("Link:", placeholder="https://www.youtube.com/watch?v=...")
            
            if st.button("🚀 Download", type="primary"):
                if FFMPEG_AVAILABLE:
                    if url and is_valid_url(url):
                        platform = detect_platform(url)
                        if platform == 'youtube':
                            format_selected = 'audio' if 'MP3' in format_type else 'video'
                            download_id = add_download(url, platform, format_selected, quality)
                            threading.Thread(
                                target=download_youtube_video,
                                args=(download_id, url, format_selected, quality)
                            ).start()
                            st.success("🎉 Iniciado!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Link inválido")
                    else:
                        st.error("❌ Insira um link")
                else:
                    st.error("❌ FFmpeg indisponível")
        
        else:  # Arquivo Local
            st.markdown("### 📁 Converter")
            
            uploaded_file = st.file_uploader(
                "Arquivo:",
                type=['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm', 'm4v']
            )
            
            if uploaded_file is not None:
                file_size = len(uploaded_file.getvalue())
                st.info(f"📄 {uploaded_file.name} ({format_file_size(file_size)})")
                
                if st.button("🎵 Converter MP3", type="primary"):
                    if FFMPEG_AVAILABLE:
                        file_path = os.path.join(UPLOADS_DIR, uploaded_file.name)
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        download_id = add_download(file_path, 'local', 'audio', 'best', is_local_file=True)
                        
                        threading.Thread(
                            target=convert_local_to_mp3,
                            args=(file_path, download_id)
                        ).start()
                        
                        st.success("🎉 Iniciado!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ FFmpeg indisponível")
    
    # Downloads
    st.markdown("## 📋 Downloads")
    
    downloads = get_downloads()
    
    if downloads:
        for download in downloads:
            (id, url, title, platform, format_type, quality, status, progress, 
             filename, file_size, error_message, created_at, is_local_file) = download
            
            with st.container():
                st.markdown('<div class="modern-card">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    display_title = title if title else ("Arquivo Local" if is_local_file else "Processando...")
                    st.markdown(f"**{display_title}**")
                    
                    if is_local_file:
                        st.caption(f"📁 {os.path.basename(url)}")
                    else:
                        st.caption(f"🔗 YouTube • {quality}")
                
                with col2:
                    if status == 'completed':
                        st.markdown('<span class="status-completed">✅ OK</span>', unsafe_allow_html=True)
                    elif status == 'failed':
                        st.markdown('<span class="status-failed">❌ Erro</span>', unsafe_allow_html=True)
                    elif status == 'downloading':
                        st.markdown('<span class="status-downloading">⏬ Baixando</span>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span class="status-pending">⏳ Aguardando</span>', unsafe_allow_html=True)
                
                with col3:
                    if st.button("🗑️", key=f"delete_{id}"):
                        delete_download(id)
                        st.rerun()
                
                if status == 'downloading':
                    st.progress(progress / 100)
                    st.caption(f"Progresso: {progress}%")
                
                if filename and file_size:
                    st.caption(f"📄 {filename} ({file_size})")
                
                if status == 'completed' and filename:
                    file_path = os.path.join(DOWNLOADS_DIR, filename)
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as file:
                            mime_type = "audio/mpeg" if filename.endswith('.mp3') else "video/mp4"
                            st.download_button(
                                label="⬇️ Download",
                                data=file,
                                file_name=filename,
                                mime=mime_type,
                                key=f"download_{id}"
                            )
                
                if error_message:
                    st.error(f"Erro: {error_message}")
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        if any(download[6] == 'downloading' for download in downloads):
            time.sleep(2)
            st.rerun()
    else:
        st.info("🎵 Nenhum download. Use o painel lateral.")

if __name__ == "__main__":
    main()
