'use client'

import { useEffect, useState, useRef, useCallback } from 'react'
import { QuranReader } from '../components/QuranReader'

interface BestMatch {
  surah_no: number
  ayah_no: number
  text_ar: string
  score: number
}

interface TimelineAyah {
  surah_no: number
  ayah_no: number
  text_ar: string
  start_ms: number | null
  end_ms: number | null
  matched_ratio: number
}

interface LiveUpdate {
  type: "update" | "error"
  elapsed_ms: number
  best: BestMatch | null
  current: TimelineAyah | null
  timeline: TimelineAyah[]
  transcript_partial: string
  state: "tracking" | "uncertain"
  message?: string
}

export default function Home() {
  const [isRecording, setIsRecording] = useState(false)
  const [isLiveTracking, setIsLiveTracking] = useState(false)
  const [recordingTime, setRecordingTime] = useState(0)
  const [result, setResult] = useState<any>(null)
  const [resultTrack, setResultTrack] = useState<any>(null)

  // Live Tracking States
  const [liveState, setLiveState] = useState<"disconnected" | "warming_up" | "tracking" | "uncertain" | "error">("disconnected")
  const [liveUpdate, setLiveUpdate] = useState<LiveUpdate | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)

  // Reader state
  const [selectedSurah, setSelectedSurah] = useState<number | null>(null) // Dynamic start (no default surah)
  const [currentAyah, setCurrentAyah] = useState<number | undefined>(undefined)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const timerRef = useRef<NodeJS.Timeout | null>(null)

  const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'

  // Auto-start on mount
  useEffect(() => {
    // Biraz bekleyerek mikrofon izni penceresinin kullanıcıyı yormamasını ve sayfanın yüklenmesini sağla
    const timer = setTimeout(() => {
      if (!isLiveTracking) {
        startLiveTracking()
      }
    }, 1000)

    return () => {
      clearTimeout(timer)
      stopRecording()
      stopLiveTracking()
    }
  }, [])

  // Cleanup on unmount

  // Timer logic
  useEffect(() => {
    let interval: NodeJS.Timeout
    if (isRecording || isLiveTracking) {
      interval = setInterval(() => {
        setRecordingTime((prev) => prev + 1)
      }, 1000)
    } else {
      setRecordingTime(0)
    }
    return () => clearInterval(interval)
  }, [isRecording, isLiveTracking])

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  // --- RECORDING (INFER) ---
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream)
      mediaRecorderRef.current = mediaRecorder
      audioChunksRef.current = []

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data)
        }
      }

      mediaRecorder.start()
      setIsRecording(true)
      setError(null)
      setResult(null)
    } catch (err) {
      setError('Mikrofon erişimi sağlanamadı')
      console.error(err)
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' })
        setIsRecording(false)
        await sendAudioToBackend(audioBlob)

        // Stop all tracks
        mediaRecorderRef.current?.stream.getTracks().forEach(track => track.stop())
      }
    }
  }

  const sendAudioToBackend = async (audioBlob: Blob) => {
    const formData = new FormData()
    formData.append('file', audioBlob, 'recording.wav')

    try {
      const res = await fetch(`${apiBase}/quran/infer`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) throw new Error('Sunucu hatası')

      const data = await res.json()
      setResult(data)
      if (data.best) {
        setCurrentAyah(data.best.ayah_no)
      }
    } catch (err) {
      setError('Analiz yapılamadı')
      console.error(err)
    }
  }

  // --- LIVE TRACKING ---
  const startLiveTracking = async () => {
    try {
      if (wsRef.current?.readyState === WebSocket.OPEN) return

      setIsLiveTracking(true)
      setLiveState("warming_up")
      setError(null)
      setResult(null)
      setLiveUpdate(null)

      // WebSocket URL
      const wsUrl = apiBase.replace('http', 'ws') + '/ws/live'
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws


      ws.onopen = async () => {
        console.log("WS Connected")
        setLiveState("tracking")
        setIsProcessing(false)

        // Önce start mesajı gönder
        ws.send(JSON.stringify({
          type: "start",
          sample_rate: 16000,
          window_sec: 14,
          target_ayahs: 12
        }))

        // Audio Stream Start
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            sampleRate: 16000
          }
        })

        // AudioContext ile PCM çıkarma
        const audioContext = new AudioContext({ sampleRate: 16000 })
        const source = audioContext.createMediaStreamSource(stream)
        const processor = audioContext.createScriptProcessor(4096, 1, 1)

        processor.onaudioprocess = (e) => {
          if (ws.readyState === WebSocket.OPEN) {
            const inputData = e.inputBuffer.getChannelData(0)
            // Float32 -> Int16 PCM
            const pcm16 = new Int16Array(inputData.length)
            for (let i = 0; i < inputData.length; i++) {
              const s = Math.max(-1, Math.min(1, inputData[i]))
              pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
            }
            // Binary olarak gönder (daha hızlı)
            ws.send(pcm16.buffer)
          }
        }

        source.connect(processor)
        processor.connect(audioContext.destination)

          // Cleanup için referans sakla
          ; (wsRef.current as any)._audioContext = audioContext
          ; (wsRef.current as any)._stream = stream
      }

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)
        if (data.type === "update") {
          setLiveUpdate(data)
          if (data.best) {
            setResult((prev: any) => ({ ...prev, best: data.best })) // Reader'ı güncellemek için
            if (data.current) {
              setCurrentAyah(data.current.ayah_no)
            } else {
              setCurrentAyah(data.best.ayah_no)
            }
          }
        } else if (data.type === "error") {
          console.error("WS Error:", data.message)
        }
      }

      ws.onerror = () => {
        if (isLiveTracking) {
          setError("Bağlantı kesildi, tekrar deneniyor...")
          setLiveState("error")
        }
      }

      ws.onclose = () => {
        if (isLiveTracking) {
          setLiveState("disconnected")
          setIsLiveTracking(false)
        }
        setIsProcessing(false)

        // Stop media tracks
        if (mediaRecorderRef.current) {
          mediaRecorderRef.current.stream.getTracks().forEach(t => t.stop())
        }
      }

    } catch (err) {
      const msg = err instanceof Error ? err.message : "Live başlatılamadı"
      setError(msg)
      setLiveState("error")
      setIsLiveTracking(false)
      setIsProcessing(false)
    }
  }

  const stopLiveTracking = () => {
    setIsLiveTracking(false)
    setLiveState("disconnected")

    // AudioContext ve stream'i kapat
    if (wsRef.current) {
      const wsAny = wsRef.current as any
      if (wsAny._audioContext) {
        wsAny._audioContext.close()
      }
      if (wsAny._stream) {
        wsAny._stream.getTracks().forEach((t: MediaStreamTrack) => t.stop())
      }
      wsRef.current.close()
      wsRef.current = null
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
      mediaRecorderRef.current.stream.getTracks().forEach(t => t.stop())
    }
  }

  const toggleTracking = async () => {
    if (isProcessing) return
    setIsProcessing(true)

    if (isLiveTracking) {
      stopLiveTracking()
      setIsProcessing(false)
    } else {
      await startLiveTracking()
      // startLiveTracking içinde ws.onopen veya error handler setIsProcessing(false) yapacak
      // Ama time-out safety ekleyelim
      setTimeout(() => setIsProcessing(false), 2000)
    }
  }

  return (
    <div className="flex flex-col h-screen bg-[#0a0a0a] text-white overflow-hidden font-sans">

      {/* HEADER */}
      <header className="flex justify-between items-center px-6 py-4 bg-black/40 border-b border-white/5 backdrop-blur-md z-50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-[#d4af37] to-[#f1c40f] flex items-center justify-center shadow-[0_0_15px_rgba(212,175,55,0.3)]">
            <span className="text-black font-bold text-lg">☾</span>
          </div>
          <h1 className="text-xl font-bold tracking-wide bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
            Voice <span className="text-[#d4af37]">Quran</span>
          </h1>
        </div>

        <div className="flex items-center gap-4">
          <div className={`px-3 py-1 rounded-full text-xs font-medium border ${isLiveTracking
            ? 'bg-green-500/10 border-green-500/20 text-green-400'
            : 'bg-white/5 border-white/10 text-gray-400'
            }`}>
            {isLiveTracking ? '● Canlı Dinleme' : '● Hazır'}
          </div>
        </div>
      </header>

      {/* MAIN CONTENT AREA */}
      {/* Split Layout: Sol (Infer Result) - Sağ (Active Reader) */}
      <div className="flex-1 flex flex-col lg:flex-row relative overflow-hidden">

        {/* SOL KOLON: Infer Sonuçları (Sadece sonuç varsa) */}
        {result && (
          <div className="w-full lg:w-1/3 flex flex-col gap-6 animate-fadeIn py-8 px-6 bg-[#050505] border-r border-[#d4af37]/10 z-10 overflow-y-auto shadow-2xl">
            <div className="flex justify-between items-center pb-4 border-b border-[#d4af37]/10">
              <h2 className="text-[#d4af37] font-bold text-xl font-['Amiri']">sonuçlar</h2>
              <button onClick={() => setResult(null)} className="p-2 hover:bg-white/5 rounded-full text-gray-400 transition-colors">✕</button>
            </div>

            <div className="space-y-6">
              <div className="relative p-6 rounded-2xl bg-gradient-to-b from-[#d4af37]/10 to-transparent border border-[#d4af37]/20 group hover:border-[#d4af37]/40 transition-all">
                <label className="text-[10px] text-[#d4af37]/70 uppercase tracking-[0.2em] font-bold mb-2 block">Tespit Edilen</label>
                <div className="flex justify-between items-end mb-4">
                  <div className="flex flex-col">
                    <span className="text-4xl font-bold text-white font-['Amiri']">{result.best?.surah_no}</span>
                    <span className="text-xs text-gray-400 uppercase tracking-wider mt-1">Sure No</span>
                  </div>
                  <div className="flex flex-col items-end">
                    <span className="text-2xl font-bold text-[#d4af37] font-['Amiri']">{result.best?.ayah_no}</span>
                    <span className="text-xs text-gray-400 uppercase tracking-wider mt-1">Ayet No</span>
                  </div>
                </div>
                <div className="h-px w-full bg-gradient-to-r from-transparent via-[#d4af37]/30 to-transparent my-4" />
                <p className="text-right dir-rtl font-['Amiri'] text-xl text-gray-200 leading-loose">
                  {result.transcript_ar}
                </p>
                <div className="mt-4 flex justify-end">
                  <span className="text-[10px] px-2 py-1 rounded bg-[#d4af37]/20 text-[#d4af37] border border-[#d4af37]/20">
                    Güven: %{(result.best?.score * 100).toFixed(1)}
                  </span>
                </div>
              </div>

              {result.top3 && (
                <div>
                  <label className="text-[10px] text-gray-500 uppercase tracking-[0.2em] font-bold mb-3 block pl-2">Alternatifler</label>
                  <div className="space-y-2">
                    {result.top3.map((m: any, i: number) => (
                      <div key={i} className="flex justify-between items-center bg-white/5 p-4 rounded-xl border border-white/5 hover:border-[#d4af37]/30 hover:bg-[#d4af37]/5 transition-all cursor-pointer group"
                        onClick={() => {
                          setCurrentAyah(m.ayah_no)
                          setResult((prev: any) => ({ ...prev, best: m }))
                        }}>
                        <div className="flex items-center gap-3">
                          <span className="w-6 h-6 rounded-full bg-white/10 text-xs flex items-center justify-center text-gray-400 group-hover:text-[#d4af37] group-hover:bg-[#d4af37]/10 font-bold">{i + 1}</span>
                          <span className="text-sm text-gray-300 group-hover:text-white transition-colors">{m.surah_no}:{m.ayah_no}</span>
                        </div>
                        <span className="text-xs text-gray-500 group-hover:text-[#d4af37]">%{(m.score * 100).toFixed(0)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* SAĞ KOLON: Quran Reader (Her zaman görünür) */}
        <div className={`relative flex-1 transition-all duration-700 bg-[#0a0a0a] ${result ? 'lg:w-2/3' : 'w-full'}`}>
          <QuranReader
            surahNo={result?.best?.surah_no || resultTrack?.window?.start_surah || liveUpdate?.best?.surah_no || selectedSurah}
            currentAyahNo={currentAyah ?? undefined}
            onJumpToAyah={(ayahNo) => setCurrentAyah(ayahNo)}
          />

          {/* Live Indicator Overlay */}
          {liveState === "tracking" && (
            <div className="absolute top-6 right-6 flex items-center gap-3 bg-black/60 backdrop-blur border border-[#d4af37]/20 pl-2 pr-4 py-2 rounded-full shadow-2xl animate-fadeIn z-20">
              <div className="relative">
                <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse z-10 relative" />
                <div className="absolute inset-0 bg-red-500 rounded-full animate-ping opacity-75" />
              </div>
              <div className="flex flex-col">
                <span className="text-[#d4af37] text-[10px] uppercase font-bold tracking-wider leading-none">Canlı Takip</span>
                <span className="text-gray-400 text-[10px] leading-tight mt-1">Dinleniyor...</span>
              </div>
            </div>
          )}
        </div>

      </div>

      {/* FLOATING ACTION AREA */}
      <div className="fixed bottom-10 right-10 z-[100] flex flex-col items-center gap-6">

        {/* Transcript Preview Bubble */}
        {isLiveTracking && liveUpdate?.transcript_partial && (
          <div className="absolute bottom-28 right-0 min-w-[300px] max-w-[400px] bg-black/80 backdrop-blur-xl border border-white/10 p-4 rounded-2xl rounded-br-sm shadow-2xl animate-fadeIn origin-bottom-right">
            <p className="text-right dir-rtl font-['Amiri'] text-lg text-gray-200 leading-relaxed">
              {liveUpdate.transcript_partial}
            </p>
            <div className="mt-2 text-[10px] text-gray-500 text-left uppercase tracking-wider">Anlık Çeviri</div>
          </div>
        )}

        {/* Recording Timer */}
        {isLiveTracking && (
          <div className="bg-red-500 text-white px-4 py-2 rounded-full text-sm font-bold tracking-wider shadow-lg animate-fadeIn flex items-center gap-2">
            <span className="w-2 h-2 bg-white rounded-full animate-blink" />
            {formatTime(recordingTime)}
          </div>
        )}

        {/* Main Toggle Button (Bigger) */}
        <div className="relative group">
          {/* Pulse Effects */}
          {isLiveTracking && (
            <>
              <div className="absolute inset-0 rounded-full border border-red-500/50 animate-ripple" />
              <div className="absolute inset-0 rounded-full border border-red-500/30 animate-ripple delay-500" />
            </>
          )}

          <button
            onClick={toggleTracking}
            className={`
                    relative w-20 h-20 rounded-full flex items-center justify-center text-3xl shadow-2xl transition-all duration-300 transform hover:scale-110 active:scale-95
                    ${isLiveTracking
                ? 'bg-red-600 hover:bg-red-700 shadow-[0_4px_30px_rgba(220,38,38,0.6)]'
                : 'bg-[#d4af37] hover:bg-[#c4a030] shadow-[0_4px_30px_rgba(212,175,55,0.5)]'
              }
                `}
          >
            {isLiveTracking ? '⏹' : '🎤'}
          </button>
        </div>
      </div>

      {/* BIG START BUTTON OVERLAY (If not tracking and no result) */}
      {!isLiveTracking && !result && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fadeIn">
          <div className="text-center">
            <button
              onClick={toggleTracking}
              className="group relative px-12 py-6 bg-[#d4af37] text-black font-bold text-xl rounded-full shadow-[0_0_50px_rgba(212,175,55,0.4)] hover:shadow-[0_0_80px_rgba(212,175,55,0.6)] transition-all transform hover:scale-105 active:scale-95"
            >
              <span className="flex items-center gap-3">
                <span className="text-3xl">🎤</span>
                <span>Dinlemeyi Başlat</span>
              </span>
              <div className="absolute inset-0 rounded-full border-2 border-[#d4af37] opacity-50 animate-ping" />
            </button>
            <p className="mt-8 text-gray-300 text-sm tracking-widest uppercase">Mikrofon izni için tıklayın</p>
          </div>
        </div>
      )}

      {/* Error Toast */}
      {error && (
        <div className="fixed bottom-10 left-10 bg-red-900/90 text-white px-6 py-4 rounded-xl border border-red-500/50 shadow-2xl backdrop-blur-md animate-fadeIn z-[100] max-w-sm flex items-start gap-4">
          <span className="text-2xl">⚠️</span>
          <div>
            <h4 className="font-bold text-sm mb-1 uppercase tracking-wide opacity-80">Hata Oluştu</h4>
            <p className="text-sm opacity-90">{error}</p>
          </div>
          <button onClick={() => setError(null)} className="text-white/50 hover:text-white">✕</button>
        </div>
      )}

    </div>
  )
}
