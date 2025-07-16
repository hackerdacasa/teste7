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
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS moderno e bonito
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
        text-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    
    .subtitle {
        font-family: 'Poppins', sans-serif;
        font-size: 1.2rem;
        text-align: center;
        color: #ffffff;
        margin-bottom: 3rem;
        opacity: 0.9;
    }
    
    .modern-card {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 2rem;
        margin: 1.5rem 0;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.2);
        transition: all 0.3s ease;
    }
    
    .modern-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 40px rgba(0, 0, 0, 0.3);
    }
    
    .feature-icon {
        font-size: 3rem;
        text-align: center;
        margin-bottom: 1rem;
    }
    
    .feature-title {
        font-family: 'Poppins', sans-serif;
        font-size: 1.5rem;
        font-weight: 600;
        text-align: center;
        color: #333;
        margin-bottom: 1rem;
    }
    
    .feature-description {
        font-family: 'Poppins', sans-serif;
        color: #666;
        text-align: center;
        line-height: 1.6;
    }
    
    .quality-selector {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 15px;
        margin: 1rem 0;
    }
    
    .status-badge {
        font-family: 'Poppins', sans-serif;
        font-weight: 500;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        display: inline-block;
        margin: 0.2rem;
        font-size: 0.9rem;
    }
    
    .status-completed {
        background: linear-gradient(135deg, #4CAF50, #45a049);
        color: white;
    }
    
    .status-failed {
        background: linear-gradient(135deg, #f44336, #d32f2f);
        color: white;
    }
    
    .status-downloading {
        background: linear-gradient(135deg, #2196F3, #1976D2);
        color: white;
    }
    
    .status-pending {
        background: linear-gradient(135deg, #FF9800, #F57C00);
        color: white;
    }
    
    .download-item {
        background: rgba(255, 255, 255, 0.9);
        backdrop-filter: blur(5px);
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        border: 1px solid rgba(255, 255, 255, 0.3);
        transition: all 0.3s ease;
    }
    
    .download-item:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
    }
    
    .sidebar .stRadio > div {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.75rem 2rem;
        font-family: 'Poppins', sans-serif;
        font-weight: 500;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
    }
    
    .stSelectbox > div > div {
        background: rgba(255, 255, 255, 0.9);
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.3);
    }
    
    .stTextInput > div > div {
        background: rgba(255, 255, 255, 0.9);
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.3);
    }
    
    .upload-area {
        border: 2px dashed #667eea;
        border-radius: 20px;
        padding: 3rem;
        text-align: center;
        margin: 2rem 0;
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0.05));
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
    }
    
    .upload-area:hover {
        border-color: #4ecdc4;
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.15), rgba(255, 255, 255, 0.1));
    }
    
    .progress-container {
        background: rgba(255, 255, 255, 0.2);
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .ffmpeg-status {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
        color: white;
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

# Verificar FFmpeg
@st.cache_resource
def get_ffmpeg_info():
    try:
        # Tentar múltiplos métodos para encontrar ffmpeg
        ffmpeg_path = None
        ffprobe_path = None
        
        # Método 1: which
        try:
            ffmpeg_result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True)
            if ffmpeg_result.returncode == 0:
                ffmpeg_path = ffmpeg_result.stdout.strip()
        except:
            pass
        
        # Método 2: whereis se which falhar
        if not ffmpeg_path:
            try:
                ffmpeg_result = subprocess.run(['whereis', 'ffmpeg'], capture_output=True, text=True)
                if ffmpeg_result.returncode == 0:
                    paths = ffmpeg_result.stdout.split()
                    for path in paths:
                        if path.endswith('ffmpeg') and os.path.exists(path):
                            ffmpeg_path = path
                            break
            except:
                pass
        
        # Método 3: caminhos comuns
        if not ffmpeg_path:
            common_paths = [
                '/usr/bin/ffmpeg',
                '/usr/local/bin/ffmpeg',
                '/opt/homebrew/bin/ffmpeg',
                shutil.which('ffmpeg')
            ]
            for path in common_paths:
                if path and os.path.exists(path):
                    ffmpeg_path = path
                    break
        
        # Mesmo processo para ffprobe
        try:
            ffprobe_result = subprocess.run(['which', 'ffprobe'], capture_output=True, text=True)
            if ffprobe_result.returncode == 0:
                ffprobe_path = ffprobe_result.stdout.strip()
        except:
            pass
        
        if not ffprobe_path:
            common_paths = [
                '/usr/bin/ffprobe',
                '/usr/local/bin/ffprobe',
                '/opt/homebrew/bin/ffprobe',
                shutil.which('ffprobe')
            ]
            for path in common_paths:
                if path and os.path.exists(path):
                    ffprobe_path = path
                    break
        
        # Testar se funcionam
        if ffmpeg_path and ffprobe_path:
            test_result = subprocess.run([ffmpeg_path, '-version'], capture_output=True, text=True)
            available = test_result.returncode == 0
        else:
            available = False
            
        return {
            'available': available,
            'ffmpeg_path': ffmpeg_path,
            'ffprobe_path': ffprobe_path
        }
    except Exception as e:
        return {'available': False, 'ffmpeg_path': None, 'ffprobe_path': None, 'error': str(e)}

FFMPEG_INFO = get_ffmpeg_info()

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
    
    # Verificar colunas
    cursor.execute("PRAGMA table_info(downloads)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'is_local_file' not in columns:
        cursor.execute('ALTER TABLE downloads ADD COLUMN is_local_file BOOLEAN DEFAULT 0')
    if 'quality' not in columns:
        cursor.execute('ALTER TABLE downloads ADD COLUMN quality TEXT DEFAULT "best"')
    
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
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(url) is not None

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
            FFMPEG_INFO['ffmpeg_path'], '-i', file_path,
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
        
        # Configurar qualidade baseada na seleção
        if quality == "4K (2160p)":
            format_selector = 'bestvideo[height<=2160]+bestaudio/best[height<=2160]'
        elif quality == "1080p":
            format_selector = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
        elif quality == "720p":
            format_selector = 'bestvideo[height<=720]+bestaudio/best[height<=720]'
        elif quality == "480p":
            format_selector = 'bestvideo[height<=480]+bestaudio/best[height<=480]'
        else:  # "Melhor Disponível"
            format_selector = 'best'
        
        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s'),
            'ffmpeg_location': FFMPEG_INFO['ffmpeg_path'],
        }
        
        if format_type == 'audio':
            ydl_opts.update({
                'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio',
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
    
    # Cabeçalho moderno
    st.markdown('<h1 class="main-title">🎵 Modern MP3 Converter</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Converta vídeos do YouTube para MP3 e arquivos locais com qualidade premium</p>', unsafe_allow_html=True)
    
    # Sidebar moderna
    with st.sidebar:
        st.markdown("### 🎛️ Controles")
        
        # Status FFmpeg
        if FFMPEG_INFO['available']:
            st.markdown("""
            <div class="ffmpeg-status">
                <h4>✅ FFmpeg Ativo</h4>
                <p>Sistema pronto para conversão</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="ffmpeg-status">
                <h4>❌ FFmpeg Inativo</h4>
                <p>Verificar instalação</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Seletor de tipo
        conversion_type = st.radio(
            "Escolha o tipo de conversão:",
            ["📹 YouTube", "🎵 Arquivo Local"]
        )
        
        if conversion_type == "📹 YouTube":
            st.markdown("### 🔗 YouTube Download")
            
            # Seletor de formato
            format_type = st.selectbox(
                "Formato:",
                ["🎵 MP3 (Áudio)", "📹 MP4 (Vídeo)"]
            )
            
            # Seletor de qualidade
            if "MP4" in format_type:
                quality = st.selectbox(
                    "Qualidade do Vídeo:",
                    ["Melhor Disponível", "4K (2160p)", "1080p", "720p", "480p"]
                )
            else:
                quality = "320kbps"
                st.info("🎵 Áudio: 320kbps de alta qualidade")
            
            url = st.text_input("Link do YouTube:", placeholder="https://www.youtube.com/watch?v=...")
            
            if st.button("🚀 Iniciar Download", type="primary"):
                if FFMPEG_INFO['available']:
                    if url and is_valid_url(url):
                        platform = detect_platform(url)
                        if platform == 'youtube':
                            format_selected = 'audio' if 'MP3' in format_type else 'video'
                            download_id = add_download(url, platform, format_selected, quality)
                            threading.Thread(
                                target=download_youtube_video,
                                args=(download_id, url, format_selected, quality)
                            ).start()
                            st.success("🎉 Download iniciado!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Use um link válido do YouTube")
                    else:
                        st.error("❌ Insira um link válido")
                else:
                    st.error("❌ FFmpeg não disponível")
        
        else:  # Arquivo Local
            st.markdown("### 📁 Converter Arquivo")
            
            uploaded_file = st.file_uploader(
                "Selecione um arquivo:",
                type=['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm', 'm4v', 'mp3', 'wav', 'flac', 'aac'],
                help="Formatos suportados: MP4, AVI, MOV, WMV, FLV, MKV, WEBM, M4V, MP3, WAV, FLAC, AAC"
            )
            
            if uploaded_file is not None:
                file_size = len(uploaded_file.getvalue())
                st.info(f"📄 {uploaded_file.name} ({format_file_size(file_size)})")
                
                if st.button("🎵 Converter para MP3", type="primary"):
                    if FFMPEG_INFO['available']:
                        file_path = os.path.join(UPLOADS_DIR, uploaded_file.name)
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        download_id = add_download(file_path, 'local', 'audio', 'best', is_local_file=True)
                        
                        threading.Thread(
                            target=convert_local_to_mp3,
                            args=(file_path, download_id)
                        ).start()
                        
                        st.success("🎉 Conversão iniciada!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ FFmpeg não disponível")
    
    # Área principal - Lista de downloads
    st.markdown("## 📋 Downloads & Conversões")
    
    downloads = get_downloads()
    
    if downloads:
        for download in downloads:
            (id, url, title, platform, format_type, quality, status, progress, 
             filename, file_size, error_message, created_at, is_local_file) = download
            
            with st.container():
                st.markdown('<div class="download-item">', unsafe_allow_html=True)
                
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
                        st.markdown('<span class="status-badge status-completed">✅ Concluído</span>', unsafe_allow_html=True)
                    elif status == 'failed':
                        st.markdown('<span class="status-badge status-failed">❌ Falhou</span>', unsafe_allow_html=True)
                    elif status == 'downloading':
                        st.markdown('<span class="status-badge status-downloading">⏬ Baixando</span>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span class="status-badge status-pending">⏳ Pendente</span>', unsafe_allow_html=True)
                
                with col3:
                    if st.button("🗑️", key=f"delete_{id}", help="Deletar"):
                        delete_download(id)
                        st.rerun()
                
                # Barra de progresso
                if status == 'downloading':
                    st.markdown('<div class="progress-container">', unsafe_allow_html=True)
                    st.progress(progress / 100)
                    st.caption(f"Progresso: {progress}%")
                    st.markdown('</div>', unsafe_allow_html=True)
                
                # Informações do arquivo
                if filename and file_size:
                    st.caption(f"📄 {filename} ({file_size})")
                
                # Botão de download
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
                
                # Mostrar erro
                if error_message:
                    st.error(f"Erro: {error_message}")
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Auto-refresh
        if any(download[6] == 'downloading' for download in downloads):
            time.sleep(2)
            st.rerun()
    else:
        st.info("🎵 Nenhum download encontrado. Use o painel lateral para começar.")

if __name__ == "__main__":
    main()
