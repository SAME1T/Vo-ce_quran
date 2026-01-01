import { useEffect, useState, useRef } from 'react'

// Types
interface QuranAyah {
  surah_no: number
  ayah_no: number
  text_ar: string
  text_tr?: string
}

interface QuranSurah {
  surah_no: number
  name_ar: string
  name_tr: string
  ayahs: QuranAyah[]
}

// Arapça rakam dönüştürücü
const toArabicNumber = (n: number) => {
  const arabicNumbers = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩'];
  return n.toString().replace(/\d/g, (d) => arabicNumbers[parseInt(d)]);
}

export const QuranReader = ({
  surahNo,
  currentAyahNo,
  onJumpToAyah
}: {
  surahNo: number | null
  currentAyahNo?: number
  onJumpToAyah?: (ayahNo: number) => void
}) => {
  const [surahData, setSurahData] = useState<QuranSurah | null>(null)
  const [loading, setLoading] = useState(false)
  const activeAyahRef = useRef<HTMLDivElement>(null)

  // Sure verisini çek
  useEffect(() => {
    if (!surahNo) {
      setSurahData(null)
      return
    }

    const fetchSurah = async () => {
      try {
        setLoading(true)
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'}/quran/surah/${surahNo}`)
        if (!res.ok) throw new Error('Sure yüklenemedi')
        const data = await res.json()
        setSurahData(data)
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchSurah()
  }, [surahNo])

  // Otomatik scroll (Active Ayah)
  useEffect(() => {
    if (currentAyahNo && activeAyahRef.current) {
      activeAyahRef.current.scrollIntoView({
        behavior: 'auto',
        block: 'center'
      })
    }
  }, [currentAyahNo])

  // --- LOADING STATE ---
  if (loading && !surahData) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-[#0a0a0a]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-[#d4af37]/20 border-t-[#d4af37] rounded-full animate-spin" />
          <p className="text-[#d4af37] text-sm font-medium tracking-widest animate-pulse">SURE YÜKLENİYOR...</p>
        </div>
      </div>
    )
  }

  // --- NO DATA STATE ---
  if (!surahNo || !surahData) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center p-8 bg-[#0a0a0a]">
        <div className="decorative-frame p-10 text-center rounded-2xl backdrop-blur-md border border-[#d4af37]/20 max-w-md mx-auto">
          <h1 className="text-4xl text-[#d4af37] font-bold mb-4 font-['Amiri']">القرآن الكريم</h1>
          <p className="text-gray-400 text-sm mb-6">Sure tespit edilemedi veya yükleniyor. Dinlemeye devam edin veya manuel seçin.</p>
          <div className="w-1.5 h-1.5 bg-[#d4af37] rounded-full mx-auto animate-ping" />
        </div>
      </div>
    )
  }

  // Besmele kontrolü (Tevbe suresi hariç)
  const hasBismillah = surahData.surah_no !== 9

  return (
    <div className="w-full h-full overflow-y-auto px-4 py-8 relative" style={{ scrollBehavior: 'smooth' }}>

      {/* Sure Başlığı */}
      <div className="max-w-4xl mx-auto mb-12 relative group cursor-default">
        <div className="decorative-frame py-6 px-12 text-center rounded-lg backdrop-blur-sm bg-black/20">
          {/* Köşe Süsleri */}
          <div className="corner-ornament top-left"></div>
          <div className="corner-ornament top-right"></div>
          <div className="corner-ornament bottom-left"></div>
          <div className="corner-ornament bottom-right"></div>

          <h2 className="text-4xl text-[#d4af37] font-bold mb-2 font-['Amiri'] drop-shadow-lg">
            سورة {surahData.name_ar}
          </h2>
          <p className="text-gray-400 text-sm uppercase tracking-widest border-t border-[#d4af37]/20 pt-2 inline-block px-8 mt-2">
            {surahData.name_tr} • {surahData.ayahs.length} Ayet
          </p>
        </div>
      </div>

      <div className="max-w-4xl mx-auto space-y-10 rtl" dir="rtl">
        {/* Besmele */}
        {hasBismillah && (
          <div className="text-center mb-10 transform hover:scale-105 transition-transform duration-500">
            <p className="text-3xl text-[#d4af37]/90 font-['Amiri'] leading-relaxed drop-shadow-md">
              بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ
            </p>
          </div>
        )}

        {/* Ayet Listesi */}
        <div className="space-y-6">
          {surahData.ayahs.map((ayah, index) => {
            // Besmele zaten yukarıda gösterildiyse atla (Fatiha hariç)
            if (hasBismillah && index === 0 && surahData.surah_no !== 1) {
              return null
            }

            const isActive = currentAyahNo === ayah.ayah_no
            const isRead = currentAyahNo ? ayah.ayah_no < currentAyahNo : false

            return (
              <div
                key={ayah.ayah_no}
                ref={isActive ? activeAyahRef : null}
                onClick={() => onJumpToAyah?.(ayah.ayah_no)}
                className={`
                  relative p-4 md:p-8 rounded-2xl transition-all duration-700 cursor-pointer group
                  ${isActive
                    ? 'bg-[#d4af37]/10 border border-[#d4af37]/30 shadow-[0_0_50px_rgba(212,175,55,0.2)] scale-[1.03] z-10'
                    : 'bg-transparent border border-transparent opacity-100'
                  }
                `}
              >
                {/* Ayet Metni */}
                <p className={`
                  text-3xl md:text-5xl leading-[2.5] font-['Amiri'] text-right
                  ${isActive
                    ? 'text-white drop-shadow-[0_0_10px_rgba(212,175,55,0.5)]'
                    : isRead
                      ? 'text-white/60'
                      : 'text-white/10 group-hover:text-white/30'
                  }
                  transition-all duration-1000
                `}>
                  <span className="relative inline-block">
                    {ayah.text_ar}
                    {/* Alt Çizgi Efekti (Aktifken) */}
                    {isActive && (
                      <span className="absolute bottom-0 left-0 w-full h-0.5 bg-gradient-to-r from-transparent via-[#d4af37]/50 to-transparent animate-pulse" />
                    )}
                  </span>

                  {/* Dekoratif Ayet Sonu (۝) */}
                  <span className={`
                    verse-marker mx-4 text-3xl md:text-5xl
                    ${isActive ? 'text-[#d4af37] drop-shadow-[0_0_15px_#d4af37]' : isRead ? 'text-[#d4af37]/50' : 'text-[#d4af37]/10'}
                  `}>
                    ۝
                  </span>

                  {/* Ayet Numarası */}
                  <span className={`
                    text-base md:text-xl align-middle font-sans font-black tracking-tighter
                    ${isActive ? 'text-[#d4af37]' : isRead ? 'text-[#d4af37]/40' : 'text-[#d4af37]/10'}
                  `}>
                    {toArabicNumber(ayah.ayah_no)}
                  </span>
                </p>
              </div>
            )
          })}
        </div>

        {/* Alt boşluk */}
        <div className="h-32" />
      </div>
    </div>
  )
}
