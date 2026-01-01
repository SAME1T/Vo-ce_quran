from fastapi import FastAPI, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, Tuple, Dict, List
import logging
import os
import tempfile
from pathlib import Path
import time
import json
import struct
import numpy as np
import asyncio

# Utils import
from utils.audio import convert_to_wav
from utils.arabic_norm import normalize_ar
from utils.quran_index import (
    get_verses, 
    match_verses,
    get_surah_ayahs,
    get_context,
    get_surah_meta
)
from utils.tracking import (
    build_target_window,
    asr_words_with_timestamps,
    build_ayah_timeline
)
from utils.seq_align import align_words
from utils.wav_io import write_wav_int16

# Faster Whisper import
from faster_whisper import WhisperModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Voice Quran ML Service")

# CORS ayarları - web 3000'den gelecek
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tüm originlere izin ver (403 hatasını çözmek için)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint: helpful message and pointer to docs."""
    return JSONResponse({"ok": True, "message": "Voice Quran ML Service - see /docs and /health"})

# Global model (lazy load)
_model: Optional[WhisperModel] = None
_model_live: Optional[WhisperModel] = None  # Live için tiny model
_verses = None
_live_connection_active = False  # Tek bağlantı desteği

def get_model():
    """Whisper modelini lazy load eder (offline için base)"""
    global _model
    if _model is None:
        logger.info("Whisper modeli yükleniyor (ilk çalıştırmada indirilecek)...")
        # "base" modeli kullan (CPU'da çalışır, daha hızlı)
        # "small" daha iyi ama daha yavaş
        _model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info("✓ Whisper modeli yüklendi")
    return _model

def get_model_live():
    """Live tracking için tiny model (hızlı)"""
    global _model_live
    if _model_live is None:
        logger.info("Live Whisper modeli yükleniyor (tiny)...")
        # cpu_threads=4 ile performansı artır
        _model_live = WhisperModel("tiny", device="cpu", compute_type="int8", cpu_threads=4)
        logger.info("✓ Live Whisper modeli yüklendi")
    return _model_live

def check_quran_loaded():
    """Kuran metninin yüklenip yüklenmediğini kontrol eder"""
    global _verses
    if _verses is None:
        _verses = get_verses()
    return len(_verses) > 0

async def process_audio_to_wav(audio: UploadFile) -> Tuple[str, str]:
    """
    Audio dosyasını alır ve WAV'a dönüştürür
    
    Returns:
        (temp_input_path, temp_wav_path)
    """
    suffix = Path(audio.filename).suffix if audio.filename else ".webm"
    fd, temp_input = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    
    with open(temp_input, "wb") as f:
        content = await audio.read()
        f.write(content)
    
    logger.info(f"Dosya alındı: {audio.filename}, {len(content)} bytes")
    
    # WAV'a dönüştür
    temp_wav = convert_to_wav(temp_input)
    
    return temp_input, temp_wav

async def find_best_match(wav_path: str) -> dict:
    """
    WAV dosyasından ASR yapar ve en iyi eşleşmeyi bulur
    
    Returns:
        {
            "transcript_ar": str,
            "best": {"surah_no": int, "ayah_no": int, "text_ar": str, "score": float},
            "top3": [...]
        }
    """
    model = get_model()
    asr_start = time.time()
    
    # ASR yap (word timestamps olmadan, sadece transcript)
    segments, info = model.transcribe(
        wav_path,
        language="ar",
        beam_size=3,
        vad_filter=True
    )
    
    # Transcript'i birleştir
    transcript_parts = []
    for segment in segments:
        transcript_parts.append(segment.text.strip())
    
    transcript_ar = " ".join(transcript_parts)
    asr_seconds = time.time() - asr_start
    
    logger.info(f"ASR tamamlandı: {transcript_ar[:50]}...")
    
    # Normalize et
    transcript_norm = normalize_ar(transcript_ar)
    
    if not transcript_norm or not transcript_norm.strip():
        raise HTTPException(
            status_code=400,
            detail="ASR çıktısı boş veya normalize edilemedi"
        )
    
    # Kuran'da eşleştir
    verses = get_verses()
    matches = match_verses(transcript_norm, verses, top_k=3)
    
    if not matches:
        raise HTTPException(
            status_code=400,
            detail="Eşleşme bulunamadı"
        )
    
    # En iyi eşleşmeyi al
    best = matches[0]
    
    # Top3 hazırla
    top3 = matches[:3]
    
    return {
        "transcript_ar": transcript_ar,
        "best": {
            "surah_no": best["surah"],
            "ayah_no": best["ayah"],
            "text_ar": best["text_ar"],
            "score": best["score"]
        },
        "top3": [
            {
                "surah_no": m["surah"],
                "ayah_no": m["ayah"],
                "text_ar": m["text_ar"],
                "score": m["score"]
            }
            for m in top3
        ]
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    quran_loaded = check_quran_loaded()
    return {
        "ok": True,
        "quran_loaded": quran_loaded
    }

@app.get("/quran/meta")
async def quran_meta():
    """Kuran sure meta bilgilerini döndürür"""
    if not check_quran_loaded():
        raise HTTPException(
            status_code=400,
            detail="Quran text not found. Run: python scripts/fetch_quran_text.py"
        )
    
    meta = get_surah_meta()
    return {"surahs": meta}

@app.get("/quran/surah/{surah_no}")
async def quran_surah(surah_no: int):
    """Belirli bir surenin ayetlerini döndürür"""
    if not check_quran_loaded():
        raise HTTPException(
            status_code=400,
            detail="Quran text not found. Run: python scripts/fetch_quran_text.py"
        )
    
    if surah_no < 1 or surah_no > 114:
        raise HTTPException(
            status_code=400,
            detail="Surah number must be between 1 and 114"
        )
    
    ayahs = get_surah_ayahs(surah_no)
    
    if not ayahs:
        raise HTTPException(
            status_code=404,
            detail=f"Surah {surah_no} not found"
        )
    
    # Sure meta bilgisini al
    meta_list = get_surah_meta()
    surah_info = next((s for s in meta_list if s["surah_no"] == surah_no), None)
    
    return {
        "surah_no": surah_no,
        "name_ar": surah_info["name_ar"] if surah_info else "",
        "name_tr": surah_info["name_tr"] if surah_info else "",
        "ayahs": ayahs
    }

@app.get("/quran/context")
async def quran_context(surah_no: int, ayah_no: int, before: int = 2, after: int = 10):
    """Belirli bir ayetin etrafındaki ayetleri döndürür"""
    if not check_quran_loaded():
        raise HTTPException(
            status_code=400,
            detail="Quran text not found. Run: python scripts/fetch_quran_text.py"
        )
    
    if surah_no < 1 or surah_no > 114:
        raise HTTPException(
            status_code=400,
            detail="Surah number must be between 1 and 114"
        )
    
    context = get_context(surah_no, ayah_no, before, after)
    
    return {
        "surah_no": surah_no,
        "ayah_no": ayah_no,
        "items": context
    }

@app.post("/infer")
async def infer(audio: UploadFile = File(...)):
    """
    Ses kaydını alır, ASR yapar ve Kuran'da eşleştirme yapar
    """
    start_time = time.time()
    
    # Kuran yüklü mü kontrol et
    if not check_quran_loaded():
        raise HTTPException(
            status_code=400,
            detail="Quran text not found. Run: python scripts/fetch_quran_text.py"
        )
    
    temp_input = None
    temp_wav = None
    
    try:
        # Audio'yu WAV'a çevir
        try:
            temp_input, temp_wav = await process_audio_to_wav(audio)
            audio_seconds = time.time() - start_time
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Ses dönüştürme hatası: {str(e)}"
            )
        
        # Best match bul
        result = await find_best_match(temp_wav)
        
        total_seconds = time.time() - start_time
        
        # Sonucu döndür
        return {
            **result,
            "meta": {
                "audio_seconds": round(audio_seconds, 2),
                "asr_seconds": round(total_seconds - audio_seconds, 2),
                "total_seconds": round(total_seconds, 2),
                "note": "search-only; tracking next sprint"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Beklenmeyen hata: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Sunucu hatası: {str(e)}"
        )
    finally:
        # Temp dosyaları temizle
        for temp_file in [temp_input, temp_wav]:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass

@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """
    WebSocket live tracking endpoint
    Client PCM stream gönderir, server timeline döner
    """
    global _live_connection_active
    
    # Tek bağlantı kontrolü
    if _live_connection_active:
        await websocket.close(code=1008, reason="Another connection is active")
        return
    
    await websocket.accept()
    _live_connection_active = True
    
    try:
        # Kuran yüklü mü kontrol et
        if not check_quran_loaded():
            await websocket.send_json({
                "type": "error",
                "message": "Quran text not found. Run: python scripts/fetch_quran_text.py"
            })
            await websocket.close()
            return
        
        # Model yükle
        model = get_model_live()
        
        # Config (ilk mesajdan gelecek)
        config = None
        sample_rate = 16000
        window_sec = 8  # Daha kısa sliding window -> daha düşük gecikme
        target_ayahs = 12

        # Ring buffer
        max_buffer_seconds = 45
        buffer = bytearray()
        total_samples_received = 0
        rec_words_global: List[Dict] = []  # Global word listesi

        # State
        best_match: Optional[Dict] = None
        tgt_words: List[Dict] = []
        ayahs: List[Dict] = []
        last_update_time = time.monotonic()
        update_interval = 0.1  # 0.1 saniyede bir güncelle (daha hızlı güncelleme)
        temp_wav_files = []
        
        while True:
            try:
                # Mesaj al
                message = await websocket.receive()
                
                if "text" in message:
                    # JSON mesaj
                    data = json.loads(message["text"])
                    
                    if data.get("type") == "start":
                        # Config al
                        config = data
                        sample_rate = data.get("sample_rate", 16000)
                        window_sec = data.get("window_sec", 14)
                        target_ayahs = data.get("target_ayahs", 12)
                        
                        await websocket.send_json({
                            "type": "status",
                            "state": "warming_up",
                            "elapsed_ms": 0
                        })
                        
                    elif data.get("type") == "stop":
                        break
                    
                    elif data.get("type") == "audio":
                        # Base64 encoded audio verisi (Frontend'den geliyor)
                        import base64
                        try:
                            audio_base64 = data.get("data", "")
                            pcm_bytes = base64.b64decode(audio_base64)
                            buffer.extend(pcm_bytes)
                            total_samples_received += len(pcm_bytes) // 2
                        except Exception as e:
                            logger.error(f"Base64 decode hatası: {e}")
                
                elif "bytes" in message:
                    # PCM binary data
                    pcm_bytes = message["bytes"]
                    buffer.extend(pcm_bytes)
                    total_samples_received += len(pcm_bytes) // 2  # int16 = 2 bytes
                    
                    # Buffer overflow kontrolü
                    max_samples = max_buffer_seconds * sample_rate
                    if len(buffer) > max_samples * 2:
                        # Eski veriyi sil (son max_samples kadar tut)
                        keep_bytes = max_samples * 2
                        buffer = buffer[-keep_bytes:]
                        total_samples_received = max_samples
                    
                    # Update loop (her 1 saniyede bir)
                    current_time = time.monotonic()
                    elapsed_ms = int((total_samples_received / sample_rate) * 1000)
                    
                    if current_time - last_update_time >= update_interval:
                        last_update_time = current_time
                        
                        # Warming up (ilk 4-6 saniye)
                        if elapsed_ms < 6000:
                            await websocket.send_json({
                                "type": "status",
                                "state": "warming_up",
                                "elapsed_ms": elapsed_ms
                            })
                            continue
                        
                        # Window samples hesapla
                        window_samples = int(window_sec * sample_rate)
                        window_bytes = window_samples * 2
                        
                        if len(buffer) < window_bytes:
                            # Yeterli veri yok
                            continue
                        
                        # Son window_sec kadar sample al
                        window_buffer = buffer[-window_bytes:]
                        
                        # WAV dosyasına yaz
                        samples_int16 = np.frombuffer(window_buffer, dtype=np.int16)
                        fd, temp_wav = tempfile.mkstemp(suffix='.wav')
                        os.close(fd)
                        temp_wav_files.append(temp_wav)
                        
                        try:
                            write_wav_int16(temp_wav, samples_int16, sample_rate)
                            
                            # ASR yap
                            segments, info = model.transcribe(
                                temp_wav,
                                language="ar",
                                beam_size=1,            # Greedy decoding (En hızlı)
                                best_of=1,              # Tek deneme
                                temperature=0.0,        # Rastgelelik yok
                                condition_on_previous_text=False, # Önceki metne bakma (Hız artırır)
                                word_timestamps=True,
                                vad_filter=False        # VAD kapalı (Gecikme olmasın)
                            )
                            
                            # Transcript ve words çıkar
                            transcript_parts = []
                            rec_words_window = []
                            
                            global_offset_ms = elapsed_ms - (window_sec * 1000)
                            
                            for segment in segments:
                                transcript_parts.append(segment.text.strip())
                                
                                for word_info in segment.words:
                                    word_text = word_info.word.strip()
                                    if not word_text:
                                        continue
                                    
                                    word_norm = normalize_ar(word_text)
                                    
                                    # Global timestamp'e çevir
                                    start_ms = int((word_info.start * 1000) + global_offset_ms)
                                    end_ms = int((word_info.end * 1000) + global_offset_ms)
                                    
                                    rec_words_window.append({
                                        "w": word_norm,
                                        "raw": word_text,
                                        "start_ms": start_ms,
                                        "end_ms": end_ms
                                    })
                            
                            transcript_partial = " ".join(transcript_parts)
                            
                            # Best match bul (henüz yoksa)
                            if best_match is None:
                                transcript_norm = normalize_ar(transcript_partial)
                                if transcript_norm and transcript_norm.strip():
                                    global _verses
                                    if _verses is None:
                                        _verses = get_verses()
                                    matches = match_verses(transcript_norm, _verses, top_k=1)
                                    if matches:
                                        best_match = {
                                            "surah_no": matches[0]["surah"],
                                            "ayah_no": matches[0]["ayah"],
                                            "text_ar": matches[0]["text_ar"],
                                            "score": matches[0]["score"]
                                        }
                                        
                                        # Target window oluştur
                                        tgt_words, ayahs = build_target_window(
                                            best_match["surah_no"],
                                            best_match["ayah_no"],
                                            window_ayahs=target_ayahs
                                        )
                            
                            # Global word listesini güncelle (son 25 saniye)
                            cutoff_ms = elapsed_ms - 25000
                            rec_words_global = [
                                w for w in rec_words_global
                                if w["end_ms"] >= cutoff_ms
                            ]
                            
                            # Yeni words ekle (duplike kontrolü)
                            for new_word in rec_words_window:
                                # Aynı start_ms varsa ekleme
                                if not any(
                                    abs(w["start_ms"] - new_word["start_ms"]) < 50
                                    for w in rec_words_global
                                ):
                                    rec_words_global.append(new_word)
                            
                            # Alignment ve timeline (best match varsa)
                            timeline = []
                            current_ayah = None
                            state = "tracking"
                            
                            if best_match and tgt_words and rec_words_global:
                                try:
                                    # Alignment
                                    pairs = align_words(rec_words_global, tgt_words)
                                    
                                    # Timeline
                                    timeline = build_ayah_timeline(
                                        pairs, rec_words_global, tgt_words, ayahs
                                    )
                                    
                                    # Current ayah bul
                                    for ayah in timeline:
                                        if (
                                            ayah["start_ms"] is not None and
                                            ayah["end_ms"] is not None and
                                            elapsed_ms >= ayah["start_ms"] and
                                            elapsed_ms < ayah["end_ms"]
                                        ):
                                            current_ayah = ayah
                                            break
                                    
                                    # Bulunamazsa matched_ratio en yüksek olanı seç
                                    if current_ayah is None and timeline:
                                        current_ayah = max(
                                            timeline,
                                            key=lambda x: x.get("matched_ratio", 0)
                                        )
                                        state = "uncertain"
                                    
                                    # Mismatch/Jump Tespiti
                                    if timeline:
                                        # En iyi eşleşen ayetin oranına bak
                                        max_ratio = max(a.get("matched_ratio", 0) for a in timeline)
                                        
                                        # Eğer oran çok düşükse (%15 altı) ve yeterli kelime varsa kullanıcı baka bir sureye zıplamış olabilir
                                        if max_ratio < 0.15 and len(transcript_partial.split()) > 3:
                                            mismatch_count += 1
                                        else:
                                            mismatch_count = 0
                                        
                                        # 4 kez üst üste düşük oran gelirse sureyi sıfırla (global re-search tetikle)
                                        if mismatch_count >= 4:
                                            logger.info("Zıplama tespit edildi! Sure sıfırlanıyor...")
                                            best_match = None
                                            tgt_words = []
                                            ayahs = []
                                            mismatch_count = 0
                                            rec_words_global = [] # Geçmişi temizle ki yeni sure temiz başlasın
                                    
                                except Exception as e:
                                    logger.error(f"Alignment/timeline hatası: {e}")
                            
                            # Client'a gönder
                            await websocket.send_json({
                                "type": "update",
                                "elapsed_ms": elapsed_ms,
                                "best": best_match,
                                "current": current_ayah,
                                "timeline": timeline,
                                "transcript_partial": transcript_partial,
                                "state": state
                            })
                            
                        except Exception as e:
                            logger.error(f"ASR/timeline hatası: {e}")
                            await websocket.send_json({
                                "type": "error",
                                "message": f"Processing error: {str(e)}"
                            })
                        finally:
                            # Temp WAV dosyasını sil
                            if os.path.exists(temp_wav):
                                try:
                                    os.remove(temp_wav)
                                    if temp_wav in temp_wav_files:
                                        temp_wav_files.remove(temp_wav)
                                except:
                                    pass
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket hatası: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
                break
        
    except Exception as e:
        logger.error(f"WebSocket connection hatası: {e}", exc_info=True)
    finally:
        _live_connection_active = False
        
        # Temp dosyaları temizle
        for temp_wav in temp_wav_files:
            if os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except:
                    pass
        
        try:
            await websocket.close()
        except:
            pass

@app.post("/track")
async def track(audio: UploadFile = File(...), window_ayahs: int = 12):
    """
    Ses kaydını alır, ASR word timestamps çıkarır ve ayet bazında timeline oluşturur
    """
    start_time = time.time()
    
    # Kuran yüklü mü kontrol et
    if not check_quran_loaded():
        raise HTTPException(
            status_code=400,
            detail="Quran text not found. Run: python scripts/fetch_quran_text.py"
        )
    
    temp_input = None
    temp_wav = None
    
    try:
        # Audio'yu WAV'a çevir
        try:
            temp_input, temp_wav = await process_audio_to_wav(audio)
            audio_seconds = time.time() - start_time
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Ses dönüştürme hatası: {str(e)}"
            )
        
        # Önce best match bul (infer mantığı)
        best_result = await find_best_match(temp_wav)
        best = best_result["best"]
        
        # Target window oluştur
        tgt_words, ayahs = build_target_window(
            best["surah_no"],
            best["ayah_no"],
            window_ayahs=window_ayahs
        )
        
        if not tgt_words or not ayahs:
            raise HTTPException(
                status_code=400,
                detail="Target window oluşturulamadı"
            )
        
        # ASR word timestamps çıkar
        try:
            model = get_model()
            asr_start = time.time()
            rec_words = asr_words_with_timestamps(temp_wav, model)
            asr_seconds = time.time() - asr_start
            
            if not rec_words:
                raise HTTPException(
                    status_code=400,
                    detail="ASR word timestamps çıkarılamadı. Word timestamps desteklenmiyor olabilir."
                )
            
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"ASR word timestamps hatası: {str(e)}"
            )
        
        # Sequence alignment
        try:
            pairs = align_words(rec_words, tgt_words)
            logger.info(f"Alignment tamamlandı: {len(pairs)} pair")
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Alignment hatası: {str(e)}"
            )
        
        # Timeline oluştur
        try:
            timeline = build_ayah_timeline(pairs, rec_words, tgt_words, ayahs)
            
            if not timeline:
                raise HTTPException(
                    status_code=400,
                    detail="Timeline oluşturulamadı"
                )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Timeline oluşturma hatası: {str(e)}"
            )
        
        total_seconds = time.time() - start_time
        
        # Sonucu döndür
        return {
            "best": best,
            "window": {
                "start_surah": best["surah_no"],
                "start_ayah": best["ayah_no"],
                "count": len(ayahs)
            },
            "timeline": timeline,
            "transcript_ar": best_result["transcript_ar"],
            "meta": {
                "note": "offline tracking via ASR-word alignment",
                "audio_seconds": round(audio_seconds, 2),
                "asr_seconds": round(asr_seconds, 2),
                "total_seconds": round(total_seconds, 2),
                "asr_words": len(rec_words)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Beklenmeyen hata: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Sunucu hatası: {str(e)}"
        )
    finally:
        # Temp dosyaları temizle
        for temp_file in [temp_input, temp_wav]:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass

@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """
    WebSocket live tracking endpoint
    Client PCM stream gönderir, server timeline döner
    """
    global _live_connection_active
    
    # Tek bağlantı kontrolü
    if _live_connection_active:
        await websocket.close(code=1008, reason="Another connection is active")
        return
    
    await websocket.accept()
    _live_connection_active = True
    
    try:
        # Kuran yüklü mü kontrol et
        if not check_quran_loaded():
            await websocket.send_json({
                "type": "error",
                "message": "Quran text not found. Run: python scripts/fetch_quran_text.py"
            })
            await websocket.close()
            return
        
        # Model yükle
        model = get_model_live()
        
        # Config (ilk mesajdan gelecek)
        config = None
        sample_rate = 16000
        window_sec = 14
        target_ayahs = 12
        
        # Ring buffer
        max_buffer_seconds = 45
        buffer = bytearray()
        total_samples_received = 0
        rec_words_global: List[Dict] = []  # Global word listesi
        
        # State
        best_match: Optional[Dict] = None
        tgt_words: List[Dict] = []
        ayahs: List[Dict] = []
        last_update_time = time.monotonic()
        update_interval = 1.0  # 1 saniye
        
        # Temp dosya listesi (temizleme için)
        temp_wav_files = []
        
        while True:
            try:
                # Mesaj al
                message = await websocket.receive()
                
                if "text" in message:
                    # JSON mesaj
                    data = json.loads(message["text"])
                    
                    if data.get("type") == "start":
                        # Config al
                        config = data
                        sample_rate = data.get("sample_rate", 16000)
                        window_sec = data.get("window_sec", 14)
                        target_ayahs = data.get("target_ayahs", 12)
                        
                        await websocket.send_json({
                            "type": "status",
                            "state": "warming_up",
                            "elapsed_ms": 0
                        })
                        
                    elif data.get("type") == "stop":
                        break
                
                elif "bytes" in message:
                    # PCM binary data
                    pcm_bytes = message["bytes"]
                    buffer.extend(pcm_bytes)
                    total_samples_received += len(pcm_bytes) // 2  # int16 = 2 bytes
                    
                    # Buffer overflow kontrolü
                    max_samples = max_buffer_seconds * sample_rate
                    if len(buffer) > max_samples * 2:
                        # Eski veriyi sil (son max_samples kadar tut)
                        keep_bytes = max_samples * 2
                        buffer = buffer[-keep_bytes:]
                        total_samples_received = max_samples
                    
                    # Update loop (her 1 saniyede bir)
                    current_time = time.monotonic()
                    elapsed_ms = int((total_samples_received / sample_rate) * 1000)
                    
                    if current_time - last_update_time >= update_interval:
                        last_update_time = current_time
                        
                        # Warming up (ilk 4-6 saniye)
                        if elapsed_ms < 6000:
                            await websocket.send_json({
                                "type": "status",
                                "state": "warming_up",
                                "elapsed_ms": elapsed_ms
                            })
                            continue
                        
                        # Window samples hesapla
                        window_samples = int(window_sec * sample_rate)
                        window_bytes = window_samples * 2
                        
                        if len(buffer) < window_bytes:
                            # Yeterli veri yok
                            continue
                        
                        # Son window_sec kadar sample al
                        window_buffer = buffer[-window_bytes:]
                        
                        # WAV dosyasına yaz
                        samples_int16 = np.frombuffer(window_buffer, dtype=np.int16)
                        fd, temp_wav = tempfile.mkstemp(suffix='.wav')
                        os.close(fd)
                        temp_wav_files.append(temp_wav)
                        
                        try:
                            write_wav_int16(temp_wav, samples_int16, sample_rate)
                            
                            # ASR yap
                            segments, info = model.transcribe(
                                temp_wav,
                                language="ar",
                                beam_size=2,
                                word_timestamps=True,
                                vad_filter=True
                            )
                            
                            # Transcript ve words çıkar
                            transcript_parts = []
                            rec_words_window = []
                            
                            global_offset_ms = elapsed_ms - (window_sec * 1000)
                            
                            for segment in segments:
                                transcript_parts.append(segment.text.strip())
                                
                                for word_info in segment.words:
                                    word_text = word_info.word.strip()
                                    if not word_text:
                                        continue
                                    
                                    word_norm = normalize_ar(word_text)
                                    
                                    # Global timestamp'e çevir
                                    start_ms = int((word_info.start * 1000) + global_offset_ms)
                                    end_ms = int((word_info.end * 1000) + global_offset_ms)
                                    
                                    rec_words_window.append({
                                        "w": word_norm,
                                        "raw": word_text,
                                        "start_ms": start_ms,
                                        "end_ms": end_ms
                                    })
                            
                            transcript_partial = " ".join(transcript_parts)
                            
                            # Best match bul (henüz yoksa)
                            if best_match is None:
                                transcript_norm = normalize_ar(transcript_partial)
                                if transcript_norm and transcript_norm.strip():
                                    verses = get_verses()
                                    matches = match_verses(transcript_norm, verses, top_k=1)
                                    if matches:
                                        best_match = {
                                            "surah_no": matches[0]["surah"],
                                            "ayah_no": matches[0]["ayah"],
                                            "text_ar": matches[0]["text_ar"],
                                            "score": matches[0]["score"]
                                        }
                                        
                                        # Target window oluştur
                                        tgt_words, ayahs = build_target_window(
                                            best_match["surah_no"],
                                            best_match["ayah_no"],
                                            window_ayahs=target_ayahs
                                        )
                            
                            # Global word listesini güncelle (son 25 saniye)
                            cutoff_ms = elapsed_ms - 25000
                            rec_words_global = [
                                w for w in rec_words_global
                                if w["end_ms"] >= cutoff_ms
                            ]
                            
                            # Yeni words ekle (duplike kontrolü)
                            for new_word in rec_words_window:
                                # Aynı start_ms varsa ekleme
                                if not any(
                                    abs(w["start_ms"] - new_word["start_ms"]) < 50
                                    for w in rec_words_global
                                ):
                                    rec_words_global.append(new_word)
                            
                            # Alignment ve timeline (best match varsa)
                            timeline = []
                            current_ayah = None
                            state = "tracking"
                            
                            if best_match and tgt_words and rec_words_global:
                                try:
                                    # Alignment
                                    pairs = align_words(rec_words_global, tgt_words)
                                    
                                    # Timeline
                                    timeline = build_ayah_timeline(
                                        pairs, rec_words_global, tgt_words, ayahs
                                    )
                                    
                                    # Current ayah bul
                                    for ayah in timeline:
                                        if (
                                            ayah["start_ms"] is not None and
                                            ayah["end_ms"] is not None and
                                            elapsed_ms >= ayah["start_ms"] and
                                            elapsed_ms < ayah["end_ms"]
                                        ):
                                            current_ayah = ayah
                                            break
                                    
                                    # Bulunamazsa matched_ratio en yüksek olanı seç
                                    if current_ayah is None and timeline:
                                        current_ayah = max(
                                            timeline,
                                            key=lambda x: x.get("matched_ratio", 0)
                                        )
                                        state = "uncertain"
                                    
                                except Exception as e:
                                    logger.error(f"Alignment/timeline hatası: {e}")
                            
                            # Client'a gönder
                            await websocket.send_json({
                                "type": "update",
                                "elapsed_ms": elapsed_ms,
                                "best": best_match,
                                "current": current_ayah,
                                "timeline": timeline,
                                "transcript_partial": transcript_partial,
                                "state": state
                            })
                            
                        except Exception as e:
                            logger.error(f"ASR/timeline hatası: {e}")
                            await websocket.send_json({
                                "type": "error",
                                "message": f"Processing error: {str(e)}"
                            })
                        finally:
                            # Temp WAV dosyasını sil
                            if os.path.exists(temp_wav):
                                try:
                                    os.remove(temp_wav)
                                    if temp_wav in temp_wav_files:
                                        temp_wav_files.remove(temp_wav)
                                except:
                                    pass
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket hatası: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
                break
        
    except Exception as e:
        logger.error(f"WebSocket connection hatası: {e}", exc_info=True)
    finally:
        _live_connection_active = False
        
        # Temp dosyaları temizle
        for temp_wav in temp_wav_files:
            if os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except:
                    pass
        
        try:
            await websocket.close()
        except:
            pass
