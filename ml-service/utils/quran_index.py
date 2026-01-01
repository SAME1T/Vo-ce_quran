"""
Kuran metnini yükler ve ayet eşleştirme yapar
"""

import os
from pathlib import Path
from typing import List, Dict, Optional
from rapidfuzz import fuzz
import logging

logger = logging.getLogger(__name__)

# Global verse listesi
_verses: Optional[List[Dict]] = None
# Sure bazında cache
_verses_by_surah: Optional[Dict[int, List[Dict]]] = None

# Sure meta (114 sure)
SURAH_META = [
    {"surah_no": 1, "name_ar": "الفاتحة", "name_tr": "Fatiha"},
    {"surah_no": 2, "name_ar": "البقرة", "name_tr": "Bakara"},
    {"surah_no": 3, "name_ar": "آل عمران", "name_tr": "Al-i İmran"},
    {"surah_no": 4, "name_ar": "النساء", "name_tr": "Nisa"},
    {"surah_no": 5, "name_ar": "المائدة", "name_tr": "Maide"},
    {"surah_no": 6, "name_ar": "الأنعام", "name_tr": "En'am"},
    {"surah_no": 7, "name_ar": "الأعراف", "name_tr": "A'raf"},
    {"surah_no": 8, "name_ar": "الأنفال", "name_tr": "Enfal"},
    {"surah_no": 9, "name_ar": "التوبة", "name_tr": "Tevbe"},
    {"surah_no": 10, "name_ar": "يونس", "name_tr": "Yunus"},
    {"surah_no": 11, "name_ar": "هود", "name_tr": "Hud"},
    {"surah_no": 12, "name_ar": "يوسف", "name_tr": "Yusuf"},
    {"surah_no": 13, "name_ar": "الرعد", "name_tr": "Ra'd"},
    {"surah_no": 14, "name_ar": "إبراهيم", "name_tr": "İbrahim"},
    {"surah_no": 15, "name_ar": "الحجر", "name_tr": "Hicr"},
    {"surah_no": 16, "name_ar": "النحل", "name_tr": "Nahl"},
    {"surah_no": 17, "name_ar": "الإسراء", "name_tr": "İsra"},
    {"surah_no": 18, "name_ar": "الكهف", "name_tr": "Kehf"},
    {"surah_no": 19, "name_ar": "مريم", "name_tr": "Meryem"},
    {"surah_no": 20, "name_ar": "طه", "name_tr": "Taha"},
    {"surah_no": 21, "name_ar": "الأنبياء", "name_tr": "Enbiya"},
    {"surah_no": 22, "name_ar": "الحج", "name_tr": "Hac"},
    {"surah_no": 23, "name_ar": "المؤمنون", "name_tr": "Mü'minun"},
    {"surah_no": 24, "name_ar": "النور", "name_tr": "Nur"},
    {"surah_no": 25, "name_ar": "الفرقان", "name_tr": "Furkan"},
    {"surah_no": 26, "name_ar": "الشعراء", "name_tr": "Şuara"},
    {"surah_no": 27, "name_ar": "النمل", "name_tr": "Neml"},
    {"surah_no": 28, "name_ar": "القصص", "name_tr": "Kasas"},
    {"surah_no": 29, "name_ar": "العنكبوت", "name_tr": "Ankebut"},
    {"surah_no": 30, "name_ar": "الروم", "name_tr": "Rum"},
    {"surah_no": 31, "name_ar": "لقمان", "name_tr": "Lokman"},
    {"surah_no": 32, "name_ar": "السجدة", "name_tr": "Secde"},
    {"surah_no": 33, "name_ar": "الأحزاب", "name_tr": "Ahzab"},
    {"surah_no": 34, "name_ar": "سبأ", "name_tr": "Sebe"},
    {"surah_no": 35, "name_ar": "فاطر", "name_tr": "Fatır"},
    {"surah_no": 36, "name_ar": "يس", "name_tr": "Yasin"},
    {"surah_no": 37, "name_ar": "الصافات", "name_tr": "Saffat"},
    {"surah_no": 38, "name_ar": "ص", "name_tr": "Sad"},
    {"surah_no": 39, "name_ar": "الزمر", "name_tr": "Zümer"},
    {"surah_no": 40, "name_ar": "غافر", "name_tr": "Gafir"},
    {"surah_no": 41, "name_ar": "فصلت", "name_tr": "Fussilet"},
    {"surah_no": 42, "name_ar": "الشورى", "name_tr": "Şura"},
    {"surah_no": 43, "name_ar": "الزخرف", "name_tr": "Zuhruf"},
    {"surah_no": 44, "name_ar": "الدخان", "name_tr": "Duhan"},
    {"surah_no": 45, "name_ar": "الجاثية", "name_tr": "Casiye"},
    {"surah_no": 46, "name_ar": "الأحقاف", "name_tr": "Ahkaf"},
    {"surah_no": 47, "name_ar": "محمد", "name_tr": "Muhammed"},
    {"surah_no": 48, "name_ar": "الفتح", "name_tr": "Fetih"},
    {"surah_no": 49, "name_ar": "الحجرات", "name_tr": "Hucurat"},
    {"surah_no": 50, "name_ar": "ق", "name_tr": "Kaf"},
    {"surah_no": 51, "name_ar": "الذاريات", "name_tr": "Zariyat"},
    {"surah_no": 52, "name_ar": "الطور", "name_tr": "Tur"},
    {"surah_no": 53, "name_ar": "النجم", "name_tr": "Necm"},
    {"surah_no": 54, "name_ar": "القمر", "name_tr": "Kamer"},
    {"surah_no": 55, "name_ar": "الرحمن", "name_tr": "Rahman"},
    {"surah_no": 56, "name_ar": "الواقعة", "name_tr": "Vakıa"},
    {"surah_no": 57, "name_ar": "الحديد", "name_tr": "Hadid"},
    {"surah_no": 58, "name_ar": "المجادلة", "name_tr": "Mücadele"},
    {"surah_no": 59, "name_ar": "الحشر", "name_tr": "Haşr"},
    {"surah_no": 60, "name_ar": "الممتحنة", "name_tr": "Mümtehine"},
    {"surah_no": 61, "name_ar": "الصف", "name_tr": "Saff"},
    {"surah_no": 62, "name_ar": "الجمعة", "name_tr": "Cuma"},
    {"surah_no": 63, "name_ar": "المنافقون", "name_tr": "Münafikun"},
    {"surah_no": 64, "name_ar": "التغابن", "name_tr": "Teğabun"},
    {"surah_no": 65, "name_ar": "الطلاق", "name_tr": "Talak"},
    {"surah_no": 66, "name_ar": "التحريم", "name_tr": "Tahrim"},
    {"surah_no": 67, "name_ar": "الملك", "name_tr": "Mülk"},
    {"surah_no": 68, "name_ar": "القلم", "name_tr": "Kalem"},
    {"surah_no": 69, "name_ar": "الحاقة", "name_tr": "Hakka"},
    {"surah_no": 70, "name_ar": "المعارج", "name_tr": "Mearic"},
    {"surah_no": 71, "name_ar": "نوح", "name_tr": "Nuh"},
    {"surah_no": 72, "name_ar": "الجن", "name_tr": "Cin"},
    {"surah_no": 73, "name_ar": "المزمل", "name_tr": "Müzzemmil"},
    {"surah_no": 74, "name_ar": "المدثر", "name_tr": "Müddessir"},
    {"surah_no": 75, "name_ar": "القيامة", "name_tr": "Kıyame"},
    {"surah_no": 76, "name_ar": "الإنسان", "name_tr": "İnsan"},
    {"surah_no": 77, "name_ar": "المرسلات", "name_tr": "Mürselat"},
    {"surah_no": 78, "name_ar": "النبأ", "name_tr": "Nebe"},
    {"surah_no": 79, "name_ar": "النازعات", "name_tr": "Naziat"},
    {"surah_no": 80, "name_ar": "عبس", "name_tr": "Abese"},
    {"surah_no": 81, "name_ar": "التكوير", "name_tr": "Tekvir"},
    {"surah_no": 82, "name_ar": "الانفطار", "name_tr": "İnfitar"},
    {"surah_no": 83, "name_ar": "المطففين", "name_tr": "Mutaffifin"},
    {"surah_no": 84, "name_ar": "الانشقاق", "name_tr": "İnşikak"},
    {"surah_no": 85, "name_ar": "البروج", "name_tr": "Buruc"},
    {"surah_no": 86, "name_ar": "الطارق", "name_tr": "Tarık"},
    {"surah_no": 87, "name_ar": "الأعلى", "name_tr": "A'la"},
    {"surah_no": 88, "name_ar": "الغاشية", "name_tr": "Gaşiye"},
    {"surah_no": 89, "name_ar": "الفجر", "name_tr": "Fecr"},
    {"surah_no": 90, "name_ar": "البلد", "name_tr": "Beled"},
    {"surah_no": 91, "name_ar": "الشمس", "name_tr": "Şems"},
    {"surah_no": 92, "name_ar": "الليل", "name_tr": "Leyl"},
    {"surah_no": 93, "name_ar": "الضحى", "name_tr": "Duha"},
    {"surah_no": 94, "name_ar": "الشرح", "name_tr": "İnşirah"},
    {"surah_no": 95, "name_ar": "التين", "name_tr": "Tin"},
    {"surah_no": 96, "name_ar": "العلق", "name_tr": "Alak"},
    {"surah_no": 97, "name_ar": "القدر", "name_tr": "Kadir"},
    {"surah_no": 98, "name_ar": "البينة", "name_tr": "Beyyine"},
    {"surah_no": 99, "name_ar": "الزلزلة", "name_tr": "Zilzal"},
    {"surah_no": 100, "name_ar": "العاديات", "name_tr": "Adiyat"},
    {"surah_no": 101, "name_ar": "القارعة", "name_tr": "Karia"},
    {"surah_no": 102, "name_ar": "التكاثر", "name_tr": "Tekasür"},
    {"surah_no": 103, "name_ar": "العصر", "name_tr": "Asr"},
    {"surah_no": 104, "name_ar": "الهمزة", "name_tr": "Hümeze"},
    {"surah_no": 105, "name_ar": "الفيل", "name_tr": "Fil"},
    {"surah_no": 106, "name_ar": "قريش", "name_tr": "Kureyş"},
    {"surah_no": 107, "name_ar": "الماعون", "name_tr": "Maun"},
    {"surah_no": 108, "name_ar": "الكوثر", "name_tr": "Kevser"},
    {"surah_no": 109, "name_ar": "الكافرون", "name_tr": "Kafirun"},
    {"surah_no": 110, "name_ar": "النصر", "name_tr": "Nasr"},
    {"surah_no": 111, "name_ar": "المسد", "name_tr": "Tebbet"},
    {"surah_no": 112, "name_ar": "الإخلاص", "name_tr": "İhlas"},
    {"surah_no": 113, "name_ar": "الفلق", "name_tr": "Felak"},
    {"surah_no": 114, "name_ar": "الناس", "name_tr": "Nas"},
]

def load_quran_lines(quran_path: str) -> List[Dict]:
    """
    Kuran metnini yükler ve normalize eder
    
    Format: "surah|ayah|text" (her satır bir ayet)
    
    Returns:
        List of dict: [{"surah": int, "ayah": int, "text_ar": str, "norm": str}, ...]
    """
    verses = []
    
    if not os.path.exists(quran_path):
        logger.warning(f"Kuran dosyası bulunamadı: {quran_path}")
        return verses
    
    try:
        with open(quran_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split("|", 2)
                if len(parts) != 3:
                    logger.warning(f"Satır {line_num} geçersiz format: {line[:50]}...")
                    continue
                
                try:
                    surah = int(parts[0])
                    ayah = int(parts[1])
                    text_ar = parts[2]
                    
                    # Normalize et (utils.arabic_norm import et)
                    from utils.arabic_norm import normalize_ar
                    norm = normalize_ar(text_ar)
                    
                    verses.append({
                        "surah": surah,
                        "ayah": ayah,
                        "text_ar": text_ar,
                        "norm": norm
                    })
                except ValueError as e:
                    logger.warning(f"Satır {line_num} parse hatası: {e}")
                    continue
        
        logger.info(f"✓ {len(verses)} ayet yüklendi")
        return verses
        
    except Exception as e:
        logger.error(f"Kuran yükleme hatası: {e}")
        return verses

def get_verses() -> List[Dict]:
    """Global verse listesini döndürür (lazy load)"""
    global _verses
    
    if _verses is None:
        # Proje root dizinini bul
        utils_dir = Path(__file__).parent
        project_root = utils_dir.parent
        quran_path = project_root / "quran" / "quran_tanzil.txt"
        
        _verses = load_quran_lines(str(quran_path))
    
    return _verses

def get_verses_by_surah() -> Dict[int, List[Dict]]:
    """Sure bazında cache oluşturur ve döndürür"""
    global _verses_by_surah
    
    if _verses_by_surah is None:
        verses = get_verses()
        _verses_by_surah = {}
        
        for verse in verses:
            surah_no = verse["surah"]
            if surah_no not in _verses_by_surah:
                _verses_by_surah[surah_no] = []
            _verses_by_surah[surah_no].append(verse)
        
        # Her sure içindeki ayetleri ayah numarasına göre sırala
        for surah_no in _verses_by_surah:
            _verses_by_surah[surah_no].sort(key=lambda x: x["ayah"])
    
    return _verses_by_surah

def get_surah_ayahs(surah_no: int) -> List[Dict]:
    """Belirli bir surenin ayetlerini döndürür"""
    verses_by_surah = get_verses_by_surah()
    
    if surah_no not in verses_by_surah:
        return []
    
    return [
        {
            "ayah_no": verse["ayah"],
            "text_ar": verse["text_ar"]
        }
        for verse in verses_by_surah[surah_no]
    ]

def get_context(surah_no: int, ayah_no: int, before: int = 2, after: int = 10) -> List[Dict]:
    """Belirli bir ayetin etrafındaki ayetleri döndürür"""
    verses_by_surah = get_verses_by_surah()
    
    if surah_no not in verses_by_surah:
        return []
    
    surah_verses = verses_by_surah[surah_no]
    
    # Mevcut ayetin index'ini bul
    current_idx = None
    for idx, verse in enumerate(surah_verses):
        if verse["ayah"] == ayah_no:
            current_idx = idx
            break
    
    if current_idx is None:
        return []
    
    # Önceki ve sonraki ayetleri al
    start_idx = max(0, current_idx - before)
    end_idx = min(len(surah_verses), current_idx + after + 1)
    
    context_verses = surah_verses[start_idx:end_idx]
    
    return [
        {
            "surah_no": surah_no,
            "ayah_no": verse["ayah"],
            "text_ar": verse["text_ar"]
        }
        for verse in context_verses
    ]

def get_surah_meta() -> List[Dict]:
    """Tüm surelerin meta bilgilerini döndürür"""
    verses_by_surah = get_verses_by_surah()
    
    meta_list = []
    for surah_info in SURAH_META:
        surah_no = surah_info["surah_no"]
        ayah_count = len(verses_by_surah.get(surah_no, []))
        
        meta_list.append({
            "surah_no": surah_no,
            "name_ar": surah_info["name_ar"],
            "name_tr": surah_info["name_tr"],
            "ayah_count": ayah_count
        })
    
    return meta_list

def match_verses(transcript_norm: str, verses: List[Dict] = None, top_k: int = 3) -> List[Dict]:
    """
    Transcript ile Kuran ayetlerini eşleştirir
    
    Args:
        transcript_norm: Normalize edilmiş transcript
        verses: Ayet listesi (None ise global listeyi kullanır)
        top_k: En iyi kaç sonuç döndürülecek
    
    Returns:
        List of dict: [{"surah": int, "ayah": int, "text_ar": str, "score": float}, ...]
        Score 0-100 arası
    """
    if verses is None:
        verses = get_verses()
    
    if not transcript_norm or not transcript_norm.strip():
        return []
    
    if not verses:
        return []
    
    # Her ayet için skor hesapla
    scored = []
    for verse in verses:
        # partial_ratio kullan (kısmi eşleşme için)
        score = fuzz.partial_ratio(transcript_norm, verse["norm"])
        scored.append({
            "surah": verse["surah"],
            "ayah": verse["ayah"],
            "text_ar": verse["text_ar"],
            "score": score
        })
    
    # Score'a göre sırala (yüksekten düşüğe)
    scored.sort(key=lambda x: x["score"], reverse=True)
    
    # Top K al
    return scored[:top_k]

