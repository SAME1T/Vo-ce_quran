# Voice Quran - Web MVP (Sprint-5: Auto-Open Reader + Auto-Jump)

Hafızlara yardımcı Kuran okuma takip uygulaması. Mikrofonla ses kaydı yapıp backend'e göndererek hangi surenin hangi ayetinde olduğunu gösterir. **Sprint-5** ile artık otomatik Kur'an ekranı açma, auto-jump ve reader panel özellikleri eklendi.

## Proje Yapısı

```
Voıce_quran/
  ├── web/              # Next.js frontend
  ├── ml-service/       # FastAPI backend
  │   ├── quran/        # Kuran metni dosyası
  │   ├── scripts/       # Yardımcı scriptler
  │   └── utils/         # Utility modülleri
  │       ├── audio.py
  │       ├── arabic_norm.py
  │       ├── quran_index.py
  │       ├── seq_align.py    # DP alignment (Sprint-3)
  │       ├── tracking.py     # Timeline tracking (Sprint-3)
  │       └── wav_io.py       # PCM16 WAV yazma (Sprint-4)
  ├── web/
  │   └── public/
  │       └── worklets/
  │           └── pcm-processor.js  # AudioWorklet (Sprint-4)
  ├── README.md
  └── .gitignore
```

## Özellikler (Sprint-5)

- ✅ Web arayüzünde Record / Stop / Send / Track / **Start Live** butonları
- ✅ Tarayıcı mikrofonundan ses kaydı (MediaRecorder)
- ✅ Webm/opus -> WAV 16kHz mono dönüştürme (FFmpeg)
- ✅ ASR ile Arapça transkript çıkarma (Faster Whisper)
- ✅ Kuran metninde en yakın ayet(ler)i bulma (rapidfuzz)
- ✅ ASR word timestamps çıkarma (Sprint-3)
- ✅ Sequence alignment (DP) ile ASR kelimelerini hedef metne hizalama (Sprint-3)
- ✅ Ayet bazında timeline oluşturma (start_ms/end_ms) (Sprint-3)
- ✅ Audio player + playback highlight (Sprint-3)
- ✅ **WebSocket canlı takip** (Sprint-4)
- ✅ **PCM stream (AudioWorklet)** ile gerçek zamanlı ses gönderimi (Sprint-4)
- ✅ **Sliding window ASR** (her 1 saniyede son 14 saniye işlenir) (Sprint-4)
- ✅ **Canlı timeline güncellemesi** (Sprint-4)
- ✅ **Live highlight** aktif ayete (Sprint-4)
- ✅ **Quran Reader Component** (Sprint-5)
- ✅ **Auto-Open Reader** - Eşleşme geldiğinde otomatik sure açılır (Sprint-5)
- ✅ **Auto-Jump** - Current ayet otomatik highlight + scroll (Sprint-5)
- ✅ **Quran API Endpoints** - Backend'den sure/ayet verisi çekme (Sprint-5)

## Sistem Gereksinimleri

### Doğrulanan Sürümler
- **Python:** 3.12.6+ (Minimum: 3.11+ önerilir)
- **pip:** 25.3+
- **Node:** v18.20.8+ (LTS önerilir)
- **npm:** 10.8.2+

### Hızlı Kontrol (Doctor Script)
```powershell
cd C:\Users\The Coder Farmer\Desktop\Voıce_quran
.\scripts\doctor.ps1
```

Bu script:
- ✅ Python/Node sürümlerini kontrol eder
- ✅ Backend sanal ortamını oluşturur/kurulum yapar
- ✅ Web bağımlılıklarını kurar
- ✅ Build testleri yapar
- ✅ Eksik dosyaları oluşturur (.env.local, requirements.lock.txt)
- ✅ Kuran metnini indirir (yoksa)
- ✅ Import testleri yapar

## Kurulum ve Çalıştırma

### Backend (ml-service)

1. **Sanal ortam oluştur ve aktifleştir:**
```powershell
cd .\ml-service
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. **Bağımlılıkları yükle:**
```powershell
pip install -r requirements.txt
```

**Not:** İlk kurulumda `faster-whisper` modeli indirilecek (yaklaşık 150MB). Bu normaldir ve bir kez yapılır.

3. **Kuran metnini indir:**
```powershell
python scripts/fetch_quran_text.py
```

Bu script Tanzil API'den Kuran metnini indirir ve `quran/quran_tanzil.txt` dosyasına kaydeder.

**Not:** Eğer script çalışmazsa, manuel olarak `quran/quran_tanzil.txt` dosyasını oluşturun. Format: Her satır `surah|ayah|text` şeklinde olmalı.

4. **Servisi başlat:**
```powershell
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Backend şu adreste çalışacak: `http://localhost:8000`

**Health Check:** `http://localhost:8000/health` → `{"ok": true, "quran_loaded": true}`

### Frontend (web)

1. **Bağımlılıkları yükle:**
```powershell
cd .\web
npm install
```

2. **Environment değişkenini ayarla:**

`web/.env.local` dosyası oluşturun (eğer yoksa):
```
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

3. **Geliştirme sunucusunu başlat:**
```powershell
npm run dev
```

Frontend şu adreste çalışacak: `http://localhost:3000`

## Kullanım

### Temel Akış (Infer)

1. Tarayıcıda `http://localhost:3000` adresini açın
2. **Kayıt** butonuna tıklayın (mikrofon izni verin)
3. Kuran okuyun (3-6 saniye yeterli)
4. **Durdur** butonuna tıklayın
5. **Gönder** butonuna tıklayın
6. Ekranda şunlar görünecek:
   - **ASR Transcript:** Okunan metnin transkripti
   - **En İyi Eşleşme:** En yüksek skorlu sure/ayet
   - **Kur'an Ekranı:** Otomatik açılır ve ilgili sure gösterilir (Sprint-5)
   - **Top 3 Eşleşmeler:** En iyi 3 eşleşme listesi

### Timeline Takibi (Track) - Sprint-3

1. Kayıt yaptıktan sonra **Takip Et** butonuna tıklayın
2. Backend ASR word timestamps çıkarır ve timeline oluşturur
3. Ekranda:
   - **Audio Player:** Kaydı dinleyebilirsiniz
   - **Timeline:** 12 ayetlik pencere (başlangıç ayetinden itibaren)
   - **Playback Highlight:** Oynatma sırasında aktif ayet otomatik vurgulanır
   - **Otomatik Scroll:** Aktif ayet ekranın ortasına kaydırılır
4. Timeline kartlarına tıklayarak ilgili ayete atlayabilirsiniz

## API Endpoints (Sprint-5)

### Quran API (Yeni)
- `GET /quran/meta` - Tüm surelerin meta bilgilerini döndürür
  - Response: `{"surahs": [{"surah_no": 1, "name_ar": "...", "name_tr": "...", "ayah_count": 7}, ...]}`
- `GET /quran/surah/{surah_no}` - Belirli bir surenin ayetlerini döndürür
  - Response: `{"surah_no": 1, "name_ar": "...", "name_tr": "...", "ayahs": [{"ayah_no": 1, "text_ar": "..."}, ...]}`
- `GET /quran/context?surah_no=1&ayah_no=1&before=2&after=10` - Belirli bir ayetin etrafındaki ayetleri döndürür
  - Response: `{"surah_no": 1, "ayah_no": 1, "items": [{"surah_no": 1, "ayah_no": 1, "text_ar": "..."}, ...]}`

### Mevcut Endpoints

### GET /health
Backend sağlık kontrolü ve Kuran yükleme durumu.

**Yanıt:**
```json
{
  "ok": true,
  "quran_loaded": true
}
```

### POST /infer
Ses kaydını alır, ASR yapar ve Kuran'da eşleştirme yapar.

**Request:**
- Content-Type: `multipart/form-data`
- Form field: `audio` (dosya - webm/opus/m4a desteklenir)

**Yanıt:**
```json
{
  "transcript_ar": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ",
  "best": {
    "surah_no": 1,
    "ayah_no": 1,
    "text_ar": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ",
    "score": 95.5
  },
  "top3": [...],
  "meta": {
    "audio_seconds": 0.5,
    "asr_seconds": 2.3,
    "total_seconds": 2.8,
    "note": "search-only; tracking next sprint"
  }
}
```

### POST /track (Sprint-3)
Ses kaydını alır, ASR word timestamps çıkarır ve ayet bazında timeline oluşturur.

**Request:**
- Content-Type: `multipart/form-data`
- Form field: `audio` (dosya)
- Query param: `window_ayahs` (opsiyonel, default: 12)

**Yanıt:**
```json
{
  "best": {
    "surah_no": 1,
    "ayah_no": 1,
    "text_ar": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ",
    "score": 95.5
  },
  "window": {
    "start_surah": 1,
    "start_ayah": 1,
    "count": 12
  },
  "timeline": [
    {
      "surah_no": 1,
      "ayah_no": 1,
      "text_ar": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ",
      "start_ms": 0,
      "end_ms": 1230,
      "matched_ratio": 0.85
    },
    {
      "surah_no": 1,
      "ayah_no": 2,
      "text_ar": "الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ",
      "start_ms": 1230,
      "end_ms": 4120,
      "matched_ratio": 0.72
    }
  ],
  "transcript_ar": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ...",
  "meta": {
    "note": "offline tracking via ASR-word alignment",
    "audio_seconds": 0.5,
    "asr_seconds": 3.2,
    "total_seconds": 3.7,
    "asr_words": 45
  }
}
```

**Hata Durumları:**
- `400`: Kuran metni yüklenmemiş → `fetch_quran_text.py` çalıştırın
- `400`: Ses dönüştürme hatası
- `400`: ASR hatası veya word timestamps desteklenmiyor
- `400`: Timeline oluşturulamadı

## Teknik Detaylar

### Stack
- **Frontend:** Next.js 14 (App Router) + TypeScript
- **Backend:** Python FastAPI
- **ASR:** Faster Whisper (base model, CPU)
- **Eşleştirme:** rapidfuzz (fuzzy string matching)
- **Alignment:** DP (Needleman-Wunsch benzeri) - Sprint-3
- **Ses Dönüştürme:** FFmpeg (imageio-ffmpeg ile)

### Backend Modülleri

- `utils/audio.py`: Webm/opus -> WAV 16kHz mono dönüştürme
- `utils/arabic_norm.py`: Arapça metin normalizasyonu (hareke kaldırma, karakter sadeleştirme)
- `utils/quran_index.py`: Kuran metnini yükleme ve eşleştirme
- `utils/seq_align.py`: DP sequence alignment (ASR kelimeleri <-> hedef metin) - Sprint-3
- `utils/tracking.py`: Timeline oluşturma (target window, ASR words, ayet timeline) - Sprint-3
- `utils/wav_io.py`: PCM16 int16 WAV dosyası yazma - Sprint-4
- `scripts/fetch_quran_text.py`: Kuran metnini Tanzil API'den indirme

### Frontend Modülleri

- `public/worklets/pcm-processor.js`: AudioWorkletProcessor (PCM float32 -> main thread) - Sprint-4
- `components/QuranReader.tsx`: Kur'an Reader component (auto-open, auto-scroll, highlight) - Sprint-5

### Alignment Algoritması (Sprint-3)

- **DP (Dynamic Programming)** kullanılır
- **Cost fonksiyonu:**
  - Insertion: 1
  - Deletion: 1
  - Substitution:
    - Eşit kelimeler: 0
    - Benzerlik >= 85%: 0.3 (küçük ceza)
    - Diğer: 1.0 (tam ceza)
- **Hedef:** Hedef kelimeleri ASR kelimelerine mümkün olduğunca eşlemek

### Timeline Oluşturma (Sprint-3)

1. **Target Window:** Başlangıç ayetinden itibaren N ayet (default: 12)
2. **ASR Word Timestamps:** Faster Whisper `word_timestamps=True` ile kelime bazında timestamp
3. **Alignment:** DP ile ASR kelimeleri hedef kelimelere hizalanır
4. **Ayet Timeline:** Her ayet için min(start_ms) ve max(end_ms) hesaplanır
5. **Interpolasyon:** Eşleşme olmayan ayetler için komşu ayetlerden interpolasyon

### Notlar

- **Model İndirme:** 
  - Offline için: Faster Whisper "base" modeli (~150MB)
  - Live için: Faster Whisper "tiny" modeli (~75MB, daha hızlı)
  - İlk çalıştırmada otomatik indirilir
- **Ses Formatı:** 
  - Offline: MediaRecorder `webm/opus` -> Backend WAV'a dönüştürür
  - Live: AudioWorklet ile PCM int16 stream (16kHz mono)
- **ASR Dil:** Arapça (`language="ar"`) olarak ayarlanmıştır.
- **Word Timestamps:** Faster Whisper word-level timestamps destekler. `/track` ve `/ws/live` endpoint'lerinde kullanılır.
- **Eşleştirme:** `rapidfuzz.partial_ratio` kullanılır (kısmi eşleşme için uygundur).
- **Live Tracking:** 
  - Sliding window: Her 1 saniyede son 14 saniye işlenir
  - Ring buffer: Maksimum 45 saniye tutulur
  - Global word listesi: Son 25 saniye tutulur (performans için)
- **CORS:** `localhost:3000` için yapılandırıldı.

### Performans

- **ASR Süresi:** 3-6 saniyelik kayıt için yaklaşık 2-4 saniye (CPU'da)
- **Word Timestamps:** ASR'den yaklaşık 1-2 saniye ek süre
- **Alignment:** Çok hızlı (< 0.1 saniye)
- **Toplam İşlem (Track):** 5-10 saniye (ses dönüştürme + ASR + word timestamps + alignment + timeline)

### Limitasyonlar (Sprint-4)

- **Live Tracking Gecikme:** Sliding window nedeniyle ~1-2 saniye gecikme olabilir
- **Kıraat Hataları:** ASR hataları veya kıraat farklılıkları `matched_ratio`'yu düşürebilir
- **Interpolasyon:** Eşleşme olmayan ayetler için basit interpolasyon kullanılır (komşu ayetlerden)
- **Word Timestamps Doğruluğu:** Faster Whisper word timestamps yaklaşık doğrudur, %100 değildir
- **Tek Bağlantı:** WebSocket endpoint'i aynı anda tek bağlantı destekler
- **CPU Kullanımı:** Live tracking CPU'da yoğun işlem yapar (GPU kullanılabilir)

## Sorun Giderme

### "Quran text not found" hatası
```powershell
cd ml-service
python scripts/fetch_quran_text.py
```

### "FFmpeg hatası"
`imageio-ffmpeg` otomatik olarak FFmpeg binary'sini indirir. Eğer sorun devam ederse, sistem FFmpeg kurulumunu kontrol edin.

### ASR çok yavaş
Faster Whisper "base" modeli CPU'da çalışır. GPU varsa `device="cuda"` kullanılabilir (main.py'de değiştirin).

### Word timestamps çıkmıyor
Faster Whisper bazı durumlarda word timestamps üretemeyebilir. Daha uzun kayıt yapmayı deneyin veya modeli "small" olarak değiştirin.

### Timeline'da bazı ayetler "No timestamp" gösteriyor
Bu normaldir. Eşleşme olmayan ayetler için interpolasyon yapılır. `matched_ratio` düşükse, daha net okumayı deneyin.

### Eşleşme bulunamıyor
- Daha uzun kayıt yapın (5-10 saniye)
- Daha net okuyun
- Mikrofon kalitesini kontrol edin

## Smoke Test Sonuçları

### Test Senaryoları

1. **Backend Health Check:**
   ```powershell
   Invoke-WebRequest http://localhost:8000/health | Select-Object -Expand Content
   ```
   Beklenen: `{"ok":true,"quran_loaded":true}`

2. **Web Build Test:**
   ```powershell
   cd web
   npm run build
   ```
   Beklenen: Build başarılı, hata yok

3. **Frontend Test:**
   - Tarayıcı: `http://localhost:3000`
   - Record -> Stop -> Send: Transcript + Best match görünmeli
   - Track: Timeline + Audio player çalışmalı
   - Start Live: WebSocket bağlantısı + Live timeline güncellemesi

### Test Komutları

**Backend başlatma:**
```powershell
cd C:\Users\The Coder Farmer\Desktop\Voıce_quran\ml-service
.\.venv\Scripts\Activate.ps1
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Web başlatma (yeni terminal):**
```powershell
cd C:\Users\The Coder Farmer\Desktop\Voıce_quran\web
npm run dev
```

## Sprint-5 Özellikleri

### Quran Reader Component

- **Otomatik Aç:** `/infer`, `/track` veya live tracking sonucu geldiğinde otomatik olarak ilgili sure açılır
- **Auto-Scroll:** Current ayet değiştiğinde otomatik olarak ekranın ortasına scroll yapar
- **Highlight:** Aktif ayet mavi border ve farklı arka plan rengi ile highlight edilir
- **Jump to Ayah:** Ayet numarası girerek belirli bir ayete atlayabilirsiniz
- **Sure Meta:** Sure adı (Arapça + Türkçe) ve ayet sayısı gösterilir

### Quran API Endpoints

Backend'de yeni Quran API endpoint'leri eklendi:
- `/quran/meta` - Tüm surelerin meta bilgileri
- `/quran/surah/{surah_no}` - Belirli bir surenin ayetleri
- `/quran/context` - Belirli bir ayetin etrafındaki ayetler

### Auto-Open Reader

- **Checkbox:** "Otomatik Aç" checkbox'ı ile auto-open özelliğini açıp kapatabilirsiniz
- **Toggle Button:** Reader panelini manuel olarak açıp kapatabilirsiniz
- **Layout:** Reader açıkken 2 kolon layout (Sol: Sonuçlar, Sağ: Quran Reader)

### Türkçe Butonlar

Tüm butonlar Türkçe'ye çevrildi:
- **Kayıt** (Record)
- **Durdur** (Stop)
- **Gönder** (Send)
- **Takip Et** (Track)
- **Canlı Takip Başlat** (Start Live)
- **Canlı Takibi Durdur** (Stop Live)

## Sonraki Adımlar (Sprint-6+)

- [ ] Daha büyük Whisper modeli (small/medium) seçeneği
- [ ] Forced alignment (CTC) ile daha doğru word-level takip
- [ ] Çoklu bağlantı desteği (WebSocket)
- [ ] GPU desteği (CUDA) ile daha hızlı ASR
- [ ] Kullanıcı arayüzü iyileştirmeleri
- [ ] Hata düzeltme ve doğruluk skorları
- [ ] Kayıt geçmişi ve istatistikler
- [ ] Mobil uyumluluk

## Lisans

Bu proje MVP aşamasındadır.
#   V o - c e _ q u r a n  
 