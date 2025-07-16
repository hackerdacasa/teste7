import os
import yt_dlp
import logging
from datetime import datetime
from app import db, app
from models import Download

class VideoDownloader:
    def __init__(self):
        self.downloads_dir = os.path.join(os.getcwd(), 'downloads')
        
    def download_video(self, download_id, format_type=None):
        """Download video in background thread"""
        try:
            with app.app_context():
                # Update status to downloading
                download = db.session.get(Download, download_id)
                if not download:
                    return
                
                # Use format_type from database if not provided
                if format_type is None:
                    format_type = download.format_type or 'video'
                
                download.status = 'downloading'
                db.session.commit()
                
                # Configure yt-dlp options based on format type
                if format_type == 'audio':
                    ydl_opts = {
                        'outtmpl': os.path.join(self.downloads_dir, '%(title)s.%(ext)s'),
                        'format': 'bestaudio/best',
                        'noplaylist': True,
                        'extractaudio': True,
                        'audioformat': 'mp3',
                        'audioquality': '192',
                        'embed_subs': False,
                        'writesubtitles': False,
                        'writeautomaticsub': False,
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        }],
                        'progress_hooks': [lambda d: self._progress_hook(d, download_id)],
                    }
                else:
                    ydl_opts = {
                        'outtmpl': os.path.join(self.downloads_dir, '%(title)s.%(ext)s'),
                        'format': 'best[ext=mp4][height<=720]/best[ext=mp4]/best[height<=720]/best',  # Prefer MP4 format
                        'noplaylist': True,
                        'extractaudio': False,
                        'audioformat': 'mp3',
                        'embed_subs': False,
                        'writesubtitles': False,
                        'writeautomaticsub': False,
                        'postprocessors': [],
                        'progress_hooks': [lambda d: self._progress_hook(d, download_id)],
                    }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Extract info first
                    info = ydl.extract_info(download.url, download=False)
                    
                    # Update download record with video info
                    download = db.session.get(Download, download_id)
                    if download:
                        download.title = info.get('title', 'Unknown Title')
                        db.session.commit()
                    
                    # Download the video
                    ydl.download([download.url])
                    
                    # Mark as completed
                    download = db.session.get(Download, download_id)
                    if download:
                        download.status = 'completed'
                        download.progress = 100
                        download.completed_at = datetime.utcnow()
                        
                        # Try to find the downloaded file
                        filename = self._find_downloaded_file(info.get('title', 'Unknown Title'))
                        if filename:
                            download.filename = filename
                            file_path = os.path.join(self.downloads_dir, filename)
                            if os.path.exists(file_path):
                                file_size = os.path.getsize(file_path)
                                download.file_size = self._format_file_size(file_size)
                        
                        db.session.commit()
                    
                    logging.info(f"Download completed for ID: {download_id}")
                    
        except Exception as e:
            logging.error(f"Download failed for ID {download_id}: {str(e)}")
            
            # Mark as failed
            with app.app_context():
                download = db.session.get(Download, download_id)
                if download:
                    download.status = 'failed'
                    download.error_message = str(e)
                    db.session.commit()
    
    def _progress_hook(self, d, download_id):
        """Progress hook for yt-dlp"""
        if d['status'] == 'downloading':
            try:
                # Calculate progress percentage
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
                
                # Update progress in database
                with app.app_context():
                    download = db.session.get(Download, download_id)
                    if download:
                        download.progress = min(progress, 99)  # Keep at 99% until complete
                        db.session.commit()
                            
            except Exception as e:
                logging.error(f"Progress update failed: {str(e)}")
    
    def _find_downloaded_file(self, title):
        """Find downloaded file by title"""
        try:
            for file in os.listdir(self.downloads_dir):
                if file.startswith(title[:50]):  # Match first 50 characters
                    return file
        except:
            pass
        return None
    
    def _format_file_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
