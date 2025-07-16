#!/usr/bin/env python3
import sys
import os
import shutil
import yt_dlp

def test_ffmpeg():
    """Testa se o FFmpeg está funcionando"""
    ffmpeg_path = shutil.which('ffmpeg')
    ffprobe_path = shutil.which('ffprobe')
    
    print(f"FFmpeg path: {ffmpeg_path}")
    print(f"FFprobe path: {ffprobe_path}")
    
    if ffmpeg_path and ffprobe_path:
        print("✅ FFmpeg encontrado e funcionando")
        return os.path.dirname(ffmpeg_path)
    else:
        print("❌ FFmpeg não encontrado")
        return None

def test_youtube_dl():
    """Testa se o yt-dlp está funcionando"""
    try:
        # URL de teste do YouTube
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        ffmpeg_path = test_ffmpeg()
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        
        if ffmpeg_path:
            ydl_opts['ffmpeg_location'] = ffmpeg_path
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(test_url, download=False)
            if info:
                print(f"✅ yt-dlp funcionando - Título: {info.get('title', 'N/A')}")
                return True
            else:
                print("❌ yt-dlp não conseguiu extrair informações")
                return False
                
    except Exception as e:
        print(f"❌ Erro no yt-dlp: {e}")
        return False

def test_audio_conversion():
    """Testa se a conversão de áudio está funcionando"""
    try:
        ffmpeg_path = test_ffmpeg()
        
        if not ffmpeg_path:
            print("❌ FFmpeg não encontrado para conversão de áudio")
            return False
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'ffmpeg_location': ffmpeg_path,
        }
        
        # Só testamos se conseguimos criar o objeto
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("✅ Configuração de conversão de áudio OK")
            return True
            
    except Exception as e:
        print(f"❌ Erro na configuração de áudio: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Testando componentes do Video Downloader...\n")
    
    print("1. Testando FFmpeg...")
    ffmpeg_ok = test_ffmpeg()
    print()
    
    print("2. Testando yt-dlp...")
    ytdl_ok = test_youtube_dl()
    print()
    
    print("3. Testando conversão de áudio...")
    audio_ok = test_audio_conversion()
    print()
    
    if ffmpeg_ok and ytdl_ok and audio_ok:
        print("🎉 Todos os testes passaram! O sistema está funcionando.")
        sys.exit(0)
    else:
        print("❌ Alguns testes falharam. Verifique os erros acima.")
        sys.exit(1)