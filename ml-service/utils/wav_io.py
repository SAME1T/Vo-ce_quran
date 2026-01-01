"""
WAV dosyası yazma: PCM16 int16 formatında
"""

import wave
import numpy as np
from typing import Union

def write_wav_int16(
    path: str,
    samples_int16: Union[np.ndarray, list],
    sample_rate: int = 16000
) -> None:
    """
    PCM16 int16 samples'ı WAV dosyasına yazar
    
    Args:
        path: Çıkış WAV dosya yolu
        samples_int16: int16 array veya list (mono)
        sample_rate: Sample rate (default: 16000)
    """
    # numpy array'e çevir
    if isinstance(samples_int16, list):
        samples_int16 = np.array(samples_int16, dtype=np.int16)
    else:
        samples_int16 = samples_int16.astype(np.int16)
    
    # WAV dosyası yaz
    with wave.open(path, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)   # 16-bit = 2 bytes
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(samples_int16.tobytes())

