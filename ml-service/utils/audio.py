"""
Ses dosyası dönüştürme: webm/ogg/m4a -> WAV 16k mono
"""

import os
import subprocess
import tempfile
from pathlib import Path
import imageio_ffmpeg
import logging

logger = logging.getLogger(__name__)

def convert_to_wav(input_path: str, output_path: str = None) -> str:
    """
    Gelen ses dosyasını WAV 16kHz mono formatına dönüştürür
    
    Args:
        input_path: Giriş dosya yolu
        output_path: Çıkış dosya yolu (None ise temp dosya oluşturur)
    
    Returns:
        Çıkış WAV dosya yolu
    
    Raises:
        RuntimeError: Dönüşüm hatası
    """
    if output_path is None:
        # Temp dosya oluştur
        fd, output_path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
    
    # FFmpeg yolunu al
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    # FFmpeg komutu: 16kHz mono WAV
    cmd = [
        ffmpeg_exe,
        '-y',  # Overwrite output
        '-i', input_path,  # Input file
        '-ac', '1',  # Mono (1 channel)
        '-ar', '16000',  # 16kHz sample rate
        '-vn',  # No video
        output_path
    ]
    
    try:
        logger.info(f"Ses dönüştürülüyor: {input_path} -> {output_path}")
        
        # FFmpeg çalıştır
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info(f"✓ Dönüşüm tamamlandı: {output_path}")
        return output_path
        
    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg hatası: {e.stderr}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"Ses dönüştürme hatası: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

