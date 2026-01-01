"""
Tracking pipeline: ASR word timestamps + sequence alignment + ayet timeline
"""

from typing import List, Dict, Optional
from utils.quran_index import get_verses
from utils.arabic_norm import normalize_ar
from utils.seq_align import align_words
from faster_whisper import WhisperModel
import logging

logger = logging.getLogger(__name__)

def build_target_window(
    best_surah: int,
    best_ayah: int,
    window_ayahs: int = 12
) -> tuple[List[Dict], List[Dict]]:
    """
    Başlangıç ayetinden itibaren N ayetlik pencere oluşturur
    
    Args:
        best_surah: Başlangıç surah numarası
        best_ayah: Başlangıç ayah numarası
        window_ayahs: Kaç ayet alınacak
    
    Returns:
        (tgt_words, ayahs):
        - tgt_words: [{w: str, ayah_no: int, surah_no: int, ayah_local_index: int}]
        - ayahs: [{surah_no: int, ayah_no: int, text_ar: str}]
    """
    verses = get_verses()
    
    if not verses:
        return [], []
    
    # İlgili ayeti bul
    start_idx = None
    for idx, verse in enumerate(verses):
        if verse["surah"] == best_surah and verse["ayah"] == best_ayah:
            start_idx = idx
            break
    
    if start_idx is None:
        logger.warning(f"Ayet bulunamadı: Surah {best_surah}, Ayah {best_ayah}")
        return [], []
    
    # N ayet al
    window_verses = verses[start_idx:start_idx + window_ayahs]
    
    # Ayet listesi
    ayahs = [
        {
            "surah_no": v["surah"],
            "ayah_no": v["ayah"],
            "text_ar": v["text_ar"]
        }
        for v in window_verses
    ]
    
    # Kelimelere böl
    tgt_words = []
    for v in window_verses:
        # Normalize et ve kelimelere böl
        text_norm = normalize_ar(v["text_ar"])
        words = [w.strip() for w in text_norm.split() if w.strip()]
        
        # Her kelime için entry oluştur
        for word_idx, word in enumerate(words):
            tgt_words.append({
                "w": word,
                "ayah_no": v["ayah"],
                "surah_no": v["surah"],
                "ayah_local_index": word_idx
            })
    
    logger.info(f"Target window: {len(ayahs)} ayet, {len(tgt_words)} kelime")
    return tgt_words, ayahs

def asr_words_with_timestamps(
    wav_path: str,
    model: WhisperModel
) -> List[Dict]:
    """
    ASR ile word-level timestamps çıkarır
    
    Args:
        wav_path: WAV dosya yolu
        model: WhisperModel instance
    
    Returns:
        rec_words: [{w: str (norm), raw: str, start_ms: float, end_ms: float}]
    """
    logger.info("ASR word timestamps çıkarılıyor...")
    
    segments, info = model.transcribe(
        wav_path,
        language="ar",
        beam_size=3,
        word_timestamps=True,
        vad_filter=True
    )
    
    rec_words = []
    
    for segment in segments:
        for word_info in segment.words:
            word_text = word_info.word.strip()
            if not word_text:
                continue
            
            # Normalize et
            word_norm = normalize_ar(word_text)
            
            rec_words.append({
                "w": word_norm,
                "raw": word_text,
                "start_ms": word_info.start * 1000,  # saniye -> ms
                "end_ms": word_info.end * 1000
            })
    
    logger.info(f"✓ {len(rec_words)} kelime timestamp ile çıkarıldı")
    return rec_words

def build_ayah_timeline(
    pairs: List[tuple],
    rec_words: List[Dict],
    tgt_words: List[Dict],
    ayahs: List[Dict]
) -> List[Dict]:
    """
    Alignment'dan ayet bazında timeline oluşturur
    
    Args:
        pairs: align_words çıktısı
        rec_words: ASR kelimeleri
        tgt_words: Hedef kelimeler
        ayahs: Ayet listesi
    
    Returns:
        timeline: [
            {
                surah_no: int,
                ayah_no: int,
                text_ar: str,
                start_ms: float,
                end_ms: float,
                matched_ratio: float
            }
        ]
    """
    # Her ayet için timestamp'leri topla
    ayah_timestamps = {}  # (surah, ayah) -> [start_ms, end_ms, ...]
    ayah_word_counts = {}  # (surah, ayah) -> total_words, matched_words
    
    for ayah in ayahs:
        key = (ayah["surah_no"], ayah["ayah_no"])
        ayah_timestamps[key] = []
        ayah_word_counts[key] = {"total": 0, "matched": 0}
    
    # Tgt words'den ayet bazında kelime sayısı
    for tgt_w in tgt_words:
        key = (tgt_w["surah_no"], tgt_w["ayah_no"])
        ayah_word_counts[key]["total"] += 1
    
    # Pairs üzerinden geç, eşleşmeleri bul
    for i_rec, i_tgt in pairs:
        if i_tgt is not None and i_rec is not None:
            # Eşleşme var
            tgt_w = tgt_words[i_tgt]
            rec_w = rec_words[i_rec]
            
            key = (tgt_w["surah_no"], tgt_w["ayah_no"])
            ayah_timestamps[key].append(rec_w["start_ms"])
            ayah_timestamps[key].append(rec_w["end_ms"])
            ayah_word_counts[key]["matched"] += 1
    
    # Timeline oluştur
    timeline = []
    
    for ayah in ayahs:
        key = (ayah["surah_no"], ayah["ayah_no"])
        timestamps = ayah_timestamps[key]
        word_count = ayah_word_counts[key]
        
        if timestamps:
            start_ms = min(timestamps)
            end_ms = max(timestamps)
        else:
            # Eşleşme yok, komşu ayetlerden interpolasyon
            start_ms = None
            end_ms = None
        
        matched_ratio = (
            word_count["matched"] / word_count["total"]
            if word_count["total"] > 0
            else 0.0
        )
        
        timeline.append({
            "surah_no": ayah["surah_no"],
            "ayah_no": ayah["ayah_no"],
            "text_ar": ayah["text_ar"],
            "start_ms": start_ms,
            "end_ms": end_ms,
            "matched_ratio": round(matched_ratio, 2)
        })
    
    # Interpolasyon: boş timestamp'leri doldur
    for i in range(len(timeline)):
        if timeline[i]["start_ms"] is None:
            # Önceki ve sonraki ayetlerden interpolasyon
            prev_end = None
            next_start = None
            
            # Önceki ayet
            for j in range(i - 1, -1, -1):
                if timeline[j]["end_ms"] is not None:
                    prev_end = timeline[j]["end_ms"]
                    break
            
            # Sonraki ayet
            for j in range(i + 1, len(timeline)):
                if timeline[j]["start_ms"] is not None:
                    next_start = timeline[j]["start_ms"]
                    break
            
            # Interpolasyon
            if prev_end is not None and next_start is not None:
                # Eşit aralıklarla dağıt
                gap = next_start - prev_end
                n_empty = 1
                for k in range(i + 1, len(timeline)):
                    if timeline[k]["start_ms"] is None:
                        n_empty += 1
                    else:
                        break
                
                step = gap / (n_empty + 1)
                timeline[i]["start_ms"] = prev_end + step
                timeline[i]["end_ms"] = prev_end + step * 2
            elif prev_end is not None:
                # Sadece önceki var, sonrakiye kadar uzat
                timeline[i]["start_ms"] = prev_end
                timeline[i]["end_ms"] = prev_end + 1000  # 1 saniye varsayılan
            elif next_start is not None:
                # Sadece sonraki var, öncekinden başlat
                timeline[i]["start_ms"] = max(0, next_start - 1000)
                timeline[i]["end_ms"] = next_start
            else:
                # Hiçbiri yok, varsayılan
                timeline[i]["start_ms"] = 0
                timeline[i]["end_ms"] = 1000
    
    return timeline

