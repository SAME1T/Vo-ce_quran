"""
Kuran metnini Tanzil'den indirir ve parse eder.
Format: "surah|ayah|text" (her satır bir ayet)
"""

import os
import sys
import requests
from pathlib import Path

# Proje root dizinini bul
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
QURAN_DIR = PROJECT_ROOT / "quran"
QURAN_FILE = QURAN_DIR / "quran_tanzil.txt"

# Tanzil API endpoint (simple text format)
TANZIL_URL = "https://api.alquran.cloud/v1/quran/quran-uthmani"

def download_quran():
    """Tanzil'den Kuran metnini indirir ve parse eder"""
    print("Kuran metni indiriliyor...")
    
    try:
        # Tanzil API'den indir
        response = requests.get(TANZIL_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # API formatı: data.surahs[].ayahs[]
        if "data" not in data:
            raise ValueError("API yanıtında 'data' bulunamadı")
        
        data_obj = data["data"]
        
        # Format kontrolü
        if "surahs" not in data_obj:
            print(f"Debug: API yanıtı (ilk 500 karakter): {str(data)[:500]}")
            raise ValueError("API yanıtı beklenen formatta değil (surahs bulunamadı)")
        
        # Klasörü oluştur
        QURAN_DIR.mkdir(parents=True, exist_ok=True)
        
        # Sureler içindeki ayetleri parse et ve kaydet
        count = 0
        with open(QURAN_FILE, "w", encoding="utf-8") as f:
            for surah in data_obj["surahs"]:
                surah_num = surah.get("number", 0)
                ayahs = surah.get("ayahs", [])
                
                for ayah in ayahs:
                    ayah_num = ayah.get("numberInSurah", 0)
                    text = ayah.get("text", "").strip()
                    
                    # BOM karakterini temizle
                    if text.startswith('\ufeff'):
                        text = text[1:]
                    
                    if surah_num > 0 and ayah_num > 0 and text:
                        f.write(f"{surah_num}|{ayah_num}|{text}\n")
                        count += 1
        
        if count == 0:
            raise ValueError("Hiç ayet bulunamadı")
        
        print(f"✓ Kuran metni başarıyla indirildi: {QURAN_FILE}")
        print(f"✓ Toplam {count} ayet kaydedildi")
        return True
        
    except requests.RequestException as e:
        print(f"✗ İndirme hatası: {e}")
        print("\nAlternatif: Manuel olarak quran_tanzil.txt dosyasını oluşturun.")
        print("Format: Her satır 'surah|ayah|text' şeklinde olmalı.")
        return False
    except Exception as e:
        print(f"✗ Hata: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = download_quran()
    sys.exit(0 if success else 1)
