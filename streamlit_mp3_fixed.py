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
    page_title="🎵 MP3 Converter",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #FF6B6B, #4ECDC4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        font-size: 3rem;
        font-weight: bold;
        margin-bottom: 2rem;
    }
    
    .feature-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    
    .status-success { background: #4CAF50; color: white; padding: 0.5rem 1rem; border-radius: 10px; display: inline-block; margin: 0.2rem; }
    .status-error { background: #f44336; color: white; padding: 0.5rem 1rem; border-radius: 10px; display: inline-block; margin: 0.2rem; }
    .status-downloading { background: #2196F3; color: white; padding: 0.5rem 1rem; border-radius: 10px; display: inline-block; margin: 0.2rem; }
    
    .upload-area {
        border: 2px dashed #667eea;
        border-radius: 15px;
        padding: 2rem;
        text-align: center;
        margin: 1rem 0;
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
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
    """Obter informações do FFmpeg"""
    try:
        # Verificar ffmpeg
        ffmpeg_result = subprocess.run(['which', 'ffmpeg'], 
                                     capture_output=True, text=True)
        ffmpeg_path = ffmpeg_result.stdout.strip() if ffmpeg_result.returncode == 0 else None
        
        # Verificar ffprobe
        ffprobe_result = subprocess.run(['which', 'ffprobe'], 
                                      capture_output=True, text=True)
        ffprobe_path = ffprobe_result.stdout.strip() if ffprobe_result.returncode == 0 else None
        
        # Testar se funciona
        if ffmpeg_path and ffprobe_path:
            test_result = subprocess.run([ffmpeg_path, '-version'], 
                                       capture_output=True, text=True)
            available = test_result.returncode == 0
        else:
            available = False
            
        return {
            'available': available,
            'ffmpeg_path': ffmpeg_path,
            'ffprobe_path': ffprobe_path
        }
    except Exception as e:
        return {
            'available': False,
            'ffmpeg_path': None,
            'ffprobe_path': None,
            'error': str(e)
        }

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
            status TEXT DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            filename TEXT,
            file_size TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_local_file BOOLEAN DEFAULT 0
        )
    ''')
    
    # Verificar se a coluna existe
    cursor.execute("PRAGMA table_info(downloads)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'is_local_file' not in columns:
        cursor.execute('ALTER TABLE downloads ADD COLUMN is_local_file BOOLEAN DEFAULT 0')
    
    conn.commit()
    conn.close()

def add_download(url, platform, format_type, is_local_file=False):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO downloads (url, platform, format_type, is_local_file)
        VALUES (?, ?, ?, ?)
    ''', (url, platform, format_type, is_local_file))
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

# Função para converter arquivo local para MP3
def convert_local_to_mp3(file_path, download_id):
    """Converte arquivo local para MP3"""
    try:
        update_download(download_id, status='downloading', progress=10)
        
        # Obter informações do arquivo
        file_name = os.path.basename(file_path)
        name_without_ext = os.path.splitext(file_name)[0]
        
        # Caminho de saída
        output_filename = f"{name_without_ext}.mp3"
        output_path = os.path.join(DOWNLOADS_DIR, output_filename)
        
        update_download(download_id, 
                       title=name_without_ext, 
                       filename=output_filename,
                       progress=30)
        
        # Comando FFmpeg para conversão
        cmd = [
            FFMPEG_INFO['ffmpeg_path'], '-i', file_path,
            '-vn',  # Sem vídeo
            '-acodec', 'libmp3lame',  # Codec MP3
            '-b:a', '320k',  # Bitrate de áudio 320kbps
            '-ar', '44100',  # Taxa de amostragem
            '-ac', '2',  # Estéreo
            '-y',  # Sobrescrever arquivo existente
            output_path
        ]
        
        update_download(download_id, progress=50)
        
        # Executar conversão
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Obter tamanho do arquivo
            file_size = os.path.getsize(output_path)
            file_size_str = format_file_size(file_size)
            
            # Remover arquivo original
            try:
                os.remove(file_path)
            except:
                pass
            
            update_download(download_id, 
                           status='completed', 
                           progress=100,
                           file_size=file_size_str)
        else:
            update_download(download_id, 
                           status='failed', 
                           error_message=f"Erro FFmpeg: {result.stderr}")
    
    except Exception as e:
        update_download(download_id, 
                       status='failed', 
                       error_message=f"Erro: {str(e)}")

# Função de download do YouTube
def download_youtube_video(download_id, url, format_type):
    """Download de vídeo do YouTube"""
    try:
        update_download(download_id, status='downloading', progress=5)
        
        # Configuração do yt-dlp
        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s'),
            'ffmpeg_location': FFMPEG_INFO['ffmpeg_path'],
            'verbose': True,
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
                update_download(download_id, 
                               filename=filename,
                               file_size=file_size,
                               progress=95)
        
        ydl_opts['progress_hooks'] = [progress_hook]
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Obter informações do vídeo
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Título não disponível')
            
            update_download(download_id, title=title, progress=10)
            
            # Fazer download
            ydl.download([url])
            
            update_download(download_id, status='completed', progress=100)
    
    except Exception as e:
        update_download(download_id, 
                       status='failed', 
                       error_message=str(e))

# Interface principal
def main():
    # Inicializar banco
    init_db()
    
    # Título principal
    st.markdown('<h1 class="main-header">🎵 MP3 Converter</h1>', unsafe_allow_html=True)
    
    # Sidebar para controles
    with st.sidebar:
        st.markdown("### 🎛️ Controles")
        
        # Status do FFmpeg
        if FFMPEG_INFO['available']:
            st.success("✅ FFmpeg funcionando")
            st.caption(f"Caminho: {FFMPEG_INFO['ffmpeg_path']}")
        else:
            st.error("❌ FFmpeg não encontrado")
            if 'error' in FFMPEG_INFO:
                st.caption(f"Erro: {FFMPEG_INFO['error']}")
        
        st.markdown("---")
        
        # Escolher tipo de conversão
        conversion_type = st.radio(
            "Escolha o tipo de conversão:",
            ["📹 YouTube para MP3", "🎵 Arquivo Local para MP3"]
        )
        
        st.markdown("---")
        
        if conversion_type == "📹 YouTube para MP3":
            st.markdown("### 🔗 Download do YouTube")
            
            url = st.text_input("Cole o link do YouTube:", 
                              placeholder="https://www.youtube.com/watch?v=...")
            
            if st.button("🎵 Converter para MP3", type="primary"):
                if FFMPEG_INFO['available']:
                    if url and is_valid_url(url):
                        platform = detect_platform(url)
                        if platform == 'youtube':
                            download_id = add_download(url, platform, 'audio')
                            threading.Thread(
                                target=download_youtube_video,
                                args=(download_id, url, 'audio')
                            ).start()
                            st.success("🎉 Conversão iniciada!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Use um link válido do YouTube")
                    else:
                        st.error("❌ Insira um link válido")
                else:
                    st.error("❌ FFmpeg não está disponível")
        
        else:  # Arquivo Local para MP3
            st.markdown("### 📁 Converter Arquivo Local")
            
            # Área de upload melhorada
            uploaded_file = st.file_uploader(
                "Selecione um arquivo de vídeo:",
                type=['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm', 'm4v', 'mp3', 'wav', 'flac', 'aac'],
                help="Formatos suportados: MP4, AVI, MOV, WMV, FLV, MKV, WEBM, M4V, MP3, WAV, FLAC, AAC"
            )
            
            if uploaded_file is not None:
                # Mostrar informações do arquivo
                file_size = len(uploaded_file.getvalue())
                st.info(f"📄 {uploaded_file.name} ({format_file_size(file_size)})")
                
                # Área de conversão
                st.markdown("""
                <div class="upload-area">
                    <h4>🎵 Pronto para converter para MP3</h4>
                    <p>Qualidade: 320kbps • Estéreo • 44.1kHz</p>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("🎵 Converter para MP3", type="primary"):
                    if FFMPEG_INFO['available']:
                        # Salvar arquivo carregado
                        file_path = os.path.join(UPLOADS_DIR, uploaded_file.name)
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        # Criar entrada no banco
                        download_id = add_download(
                            file_path, 'local', 'audio', is_local_file=True
                        )
                        
                        # Iniciar conversão
                        threading.Thread(
                            target=convert_local_to_mp3,
                            args=(file_path, download_id)
                        ).start()
                        
                        st.success("🎉 Conversão iniciada!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ FFmpeg não está disponível")
            else:
                st.markdown("""
                <div class="upload-area">
                    <h4>📤 Arraste e solte um arquivo</h4>
                    <p>Ou clique para selecionar</p>
                </div>
                """, unsafe_allow_html=True)
    
    # Área principal - Lista de downloads
    st.markdown("## 📋 Histórico de Conversões")
    
    downloads = get_downloads()
    
    if downloads:
        for download in downloads:
            (id, url, title, platform, format_type, status, progress, 
             filename, file_size, error_message, created_at, is_local_file) = download
            
            with st.container():
                st.markdown("---")
                
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    display_title = title if title else ("Arquivo Local" if is_local_file else "Processando...")
                    st.markdown(f"**{display_title}**")
                    
                    if is_local_file:
                        st.caption(f"📁 {os.path.basename(url)}")
                    else:
                        st.caption(f"🔗 {url}")
                
                with col2:
                    if status == 'completed':
                        st.markdown('<div class="status-success">✅ Concluído</div>', unsafe_allow_html=True)
                    elif status == 'failed':
                        st.markdown('<div class="status-error">❌ Falhou</div>', unsafe_allow_html=True)
                    elif status == 'downloading':
                        st.markdown('<div class="status-downloading">⏬ Convertendo</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="status-downloading">⏳ Pendente</div>', unsafe_allow_html=True)
                
                with col3:
                    if st.button("🗑️", key=f"delete_{id}", help="Deletar"):
                        delete_download(id)
                        st.rerun()
                
                # Barra de progresso
                if status == 'downloading':
                    st.progress(progress / 100)
                    st.caption(f"Progresso: {progress}%")
                
                # Informações do arquivo
                if filename and file_size:
                    st.caption(f"📄 {filename} ({file_size})")
                
                # Botão de download
                if status == 'completed' and filename:
                    file_path = os.path.join(DOWNLOADS_DIR, filename)
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as file:
                            st.download_button(
                                label="⬇️ Download MP3",
                                data=file,
                                file_name=filename,
                                mime="audio/mpeg",
                                key=f"download_{id}"
                            )
                
                # Mostrar erro se houver
                if error_message:
                    st.error(f"Erro: {error_message}")
        
        # Auto-refresh para downloads em andamento
        if any(download[5] == 'downloading' for download in downloads):
            time.sleep(2)
            st.rerun()
    else:
        st.info("🎵 Nenhuma conversão encontrada. Use o painel lateral para iniciar uma nova conversão.")

if __name__ == "__main__":
    main()