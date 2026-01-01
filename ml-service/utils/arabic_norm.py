"""
Arapça metin normalizasyonu: hareke, diakritik ve özel karakterleri temizler
"""

import re
import unicodedata

def normalize_ar(text: str) -> str:
    """
    Arapça metni normalize eder:
    - Hareke/diakritik kaldırır
    - Tatweel (ـ) kaldırır
    - Noktalama/harici işaretleri kaldırır
    - Fazla boşlukları tek boşluğa indirir
    - Farklı elif formlarını sadeleştirir (أ إ آ -> ا)
    - ة->ه, ى->ي dönüşümleri (opsiyonel)
    """
    if not text:
        return ""
    
    # Unicode normalize (NFD -> NFC)
    text = unicodedata.normalize("NFD", text)
    
    # Hareke/diakritik kaldır (Arapça diakritik aralığı: 0x064B-0x065F, 0x0670)
    # Ayrıca şedde (0x0651) ve diğer işaretleri kaldır
    text = re.sub(r'[\u064B-\u065F\u0670\u0651\u0652\u0653\u0654\u0655\u0656\u0657\u0658\u0659\u065A\u065B\u065C\u065D\u065E\u065F]', '', text)
    
    # Tatweel (ـ) kaldır
    text = text.replace('ـ', '')
    
    # Farklı elif formlarını sadeleştir
    text = text.replace('أ', 'ا')  # elif with hamza above
    text = text.replace('إ', 'ا')  # elif with hamza below
    text = text.replace('آ', 'ا')  # elif with madda
    
    # ة -> ه (opsiyonel - bazı sistemlerde tutulur, bazılarında değiştirilir)
    text = text.replace('ة', 'ه')
    
    # ى -> ي (opsiyonel - son elif yerine ye)
    text = text.replace('ى', 'ي')
    
    # Noktalama ve özel karakterleri kaldır (Arapça metin için)
    # Sadece Arapça harfleri, rakamları ve boşlukları tut
    text = re.sub(r'[^\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF\s0-9]', '', text)
    
    # Fazla boşlukları tek boşluğa indir
    text = re.sub(r'\s+', ' ', text)
    
    # Başta/sonda boşlukları temizle
    text = text.strip()
    
    return text

