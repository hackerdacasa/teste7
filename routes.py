from flask import render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from app import app, db
from models import Download
from downloader import VideoDownloader
import threading
import os
from urllib.parse import urlparse
import re

downloader = VideoDownloader()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/downloads')
def downloads():
    downloads = Download.query.order_by(Download.created_at.desc()).all()
    return render_template('downloads.html', downloads=downloads)

@app.route('/download', methods=['POST'])
def start_download():
    url = request.form.get('url', '').strip()
    format_type = request.form.get('format', 'video')  # 'video' or 'audio'
    
    if not url:
        flash('Por favor, insira uma URL válida.', 'error')
        return redirect(url_for('index'))
    
    # Basic URL validation
    if not is_valid_url(url):
        flash('URL inválida. Por favor, insira uma URL válida do YouTube ou Instagram.', 'error')
        return redirect(url_for('index'))
    
    # Detect platform
    platform = detect_platform(url)
    if not platform:
        flash('Plataforma não suportada. Apenas YouTube e Instagram são suportados.', 'error')
        return redirect(url_for('index'))
    
    # Check if URL already exists and is not failed
    existing = Download.query.filter_by(url=url).filter(Download.status != 'failed').first()
    if existing:
        flash('Esta URL já foi baixada ou está em processo de download.', 'warning')
        return redirect(url_for('downloads'))
    
    # Create download record
    download = Download(url=url, platform=platform, format_type=format_type)
    db.session.add(download)
    db.session.commit()
    
    # Start download in background thread
    thread = threading.Thread(target=downloader.download_video, args=(download.id, format_type))
    thread.daemon = True
    thread.start()
    
    format_msg = "áudio" if format_type == "audio" else "vídeo"
    flash(f'Download de {format_msg} iniciado! Acompanhe o progresso na página de downloads.', 'success')
    return redirect(url_for('downloads'))

@app.route('/api/download/<int:download_id>')
def get_download_status(download_id):
    download = Download.query.get_or_404(download_id)
    return jsonify(download.to_dict())

@app.route('/api/downloads')
def get_all_downloads():
    downloads = Download.query.order_by(Download.created_at.desc()).all()
    return jsonify([download.to_dict() for download in downloads])

@app.route('/download_file/<int:download_id>')
def download_file(download_id):
    download = Download.query.get_or_404(download_id)
    
    if download.filename and download.status == 'completed':
        downloads_dir = os.path.join(os.getcwd(), 'downloads')
        file_path = os.path.join(downloads_dir, download.filename)
        
        if os.path.exists(file_path):
            return send_from_directory(downloads_dir, download.filename, as_attachment=True)
    
    flash('Arquivo não encontrado.', 'error')
    return redirect(url_for('downloads'))

@app.route('/delete/<int:download_id>')
def delete_download(download_id):
    download = Download.query.get_or_404(download_id)
    
    # Delete file if exists
    if download.filename:
        file_path = os.path.join('downloads', download.filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
    
    db.session.delete(download)
    db.session.commit()
    
    flash('Download removido com sucesso.', 'success')
    return redirect(url_for('downloads'))

def is_valid_url(url):
    """Check if URL is valid"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def detect_platform(url):
    """Detect if URL is from YouTube or Instagram"""
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
