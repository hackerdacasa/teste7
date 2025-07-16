#!/usr/bin/env python3
import streamlit as st
import yt_dlp
import os
import shutil
import sqlite3
import threading
import time
from datetime import datetime

# Configuração
st.set_page_config(page_title="Debug MP3", layout="wide")

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
        CREATE TABLE IF NOT EXISTS debug_downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            title TEXT,
            format_type TEXT,
            status TEXT DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            filename TEXT,
            error_message TEXT,
            logs TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def add_debug_download(url, format_type):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO debug_downloads (url, format_type)
        VALUES (?, ?)
    ''', (url, format_type))
    download_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return download_id

def update_debug_download(download_id, **kwargs):
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
        query = f"UPDATE debug_downloads SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        conn.commit()
    
    conn.close()

def get_debug_downloads():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM debug_downloads ORDER BY created_at DESC')
    downloads = cursor.fetchall()
    conn.close()
    return downloads

# Download com logs detalhados
def download_with_debug(download_id, url, format_type):
    logs = []
    
    try:
        logs.append(f"[{datetime.now()}] Iniciando download de {format_type}")
        logs.append(f"[{datetime.now()}] URL: {url}")
        logs.append(f"[{datetime.now()}] FFmpeg path: {FFMPEG_PATH}")
        
        update_debug_download(download_id, status='downloading', logs='\n'.join(logs))
        
        # Configuração
        base_opts = {
            'outtmpl': os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s'),
            'noplaylist': True,
        }
        
        if FFMPEG_PATH:
            base_opts['ffmpeg_location'] = FFMPEG_PATH
            logs.append(f"[{datetime.now()}] FFmpeg configurado: {FFMPEG_PATH}")
        
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
            logs.append(f"[{datetime.now()}] Configuração para áudio MP3 aplicada")
        else:
            ydl_opts = {
                **base_opts,
                'format': 'best[ext=mp4]/best',
            }
            logs.append(f"[{datetime.now()}] Configuração para vídeo MP4 aplicada")
        
        update_debug_download(download_id, logs='\n'.join(logs))
        
        # Extrair info
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logs.append(f"[{datetime.now()}] Extraindo informações do vídeo...")
            update_debug_download(download_id, logs='\n'.join(logs))
            
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown')
            
            logs.append(f"[{datetime.now()}] Título: {title}")
            update_debug_download(download_id, title=title, logs='\n'.join(logs))
            
            # Listar arquivos antes do download
            files_before = set(os.listdir(DOWNLOADS_DIR))
            logs.append(f"[{datetime.now()}] Arquivos antes do download: {len(files_before)}")
            
            # Download
            logs.append(f"[{datetime.now()}] Iniciando download...")
            update_debug_download(download_id, logs='\n'.join(logs))
            
            ydl.download([url])
            
            # Listar arquivos após o download
            files_after = set(os.listdir(DOWNLOADS_DIR))
            new_files = files_after - files_before
            
            logs.append(f"[{datetime.now()}] Arquivos após download: {len(files_after)}")
            logs.append(f"[{datetime.now()}] Novos arquivos: {list(new_files)}")
            
            # Encontrar arquivo
            filename = None
            
            if format_type == 'audio':
                # Procurar MP3
                mp3_files = [f for f in new_files if f.endswith('.mp3')]
                logs.append(f"[{datetime.now()}] Arquivos MP3 encontrados: {mp3_files}")
                
                if mp3_files:
                    filename = mp3_files[0]
                    logs.append(f"[{datetime.now()}] Arquivo MP3 selecionado: {filename}")
            
            if not filename and new_files:
                filename = list(new_files)[0]
                logs.append(f"[{datetime.now()}] Primeiro arquivo novo selecionado: {filename}")
            
            if filename:
                file_path = os.path.join(DOWNLOADS_DIR, filename)
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    logs.append(f"[{datetime.now()}] Arquivo encontrado: {filename} ({file_size} bytes)")
                    
                    update_debug_download(
                        download_id, 
                        status='completed', 
                        progress=100,
                        filename=filename,
                        logs='\n'.join(logs)
                    )
                else:
                    logs.append(f"[{datetime.now()}] ERRO: Arquivo não existe: {file_path}")
                    update_debug_download(download_id, status='failed', error_message='Arquivo não encontrado', logs='\n'.join(logs))
            else:
                logs.append(f"[{datetime.now()}] ERRO: Nenhum arquivo encontrado")
                update_debug_download(download_id, status='failed', error_message='Nenhum arquivo encontrado', logs='\n'.join(logs))
                
    except Exception as e:
        logs.append(f"[{datetime.now()}] ERRO: {str(e)}")
        update_debug_download(download_id, status='failed', error_message=str(e), logs='\n'.join(logs))

# Inicializar
init_db()

# Interface
st.title("🔍 Debug MP3 Download")

# Status
if FFMPEG_PATH:
    st.success(f"✅ FFmpeg: {FFMPEG_PATH}")
else:
    st.error("❌ FFmpeg não encontrado")

# Formulário
with st.form("debug_form"):
    url = st.text_input("URL de teste:")
    format_type = st.selectbox("Formato:", ["audio", "video"])
    
    if st.form_submit_button("🧪 Testar Download"):
        if url:
            download_id = add_debug_download(url, format_type)
            
            # Iniciar download em thread
            thread = threading.Thread(target=download_with_debug, args=(download_id, url, format_type))
            thread.daemon = True
            thread.start()
            
            st.success("Teste iniciado!")
            st.rerun()

# Mostrar downloads
st.header("📊 Resultados dos Testes")

downloads = get_debug_downloads()

for download in downloads:
    download_id, url, title, format_type, status, progress, filename, error_message, logs, created_at = download
    
    with st.expander(f"#{download_id} - {title or 'Carregando...'} ({format_type})"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Status:** {status}")
            st.write(f"**URL:** {url}")
            st.write(f"**Formato:** {format_type}")
            if filename:
                st.write(f"**Arquivo:** {filename}")
            if error_message:
                st.error(f"**Erro:** {error_message}")
        
        with col2:
            if filename:
                file_path = os.path.join(DOWNLOADS_DIR, filename)
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        st.download_button(
                            "📥 Baixar",
                            f.read(),
                            filename,
                            key=f"debug_download_{download_id}"
                        )
        
        # Logs detalhados
        if logs:
            st.text_area("Logs detalhados:", logs, height=200, key=f"logs_{download_id}")

# Auto-refresh
if any(d[4] in ['downloading', 'pending'] for d in downloads):
    time.sleep(2)
    st.rerun()