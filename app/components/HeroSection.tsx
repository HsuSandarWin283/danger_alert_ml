"use client"

import { useRouter } from 'next/navigation'
import { useMicrophoneContext } from "@/app/lib/MicrophoneProvider"
import { useLang } from "@/app/lib/LanguageProvider"

export default function HeroSection() {
  const router = useRouter()
  const { isRecording, recordingTime, startRecording, stopRecording, error } = useMicrophoneContext()
  const { t, lang } = useLang()

  const isBurmese = lang === 'my'

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
  }

  return (
    <section
      className="text-center py-8 sm:py-12 px-4 sm:px-6 text-white"
      style={{
        background: 'linear-gradient(to right, #000000, #1f2937)'
      }}
    >
      <h1 className={`font-bold mb-3 sm:mb-5 leading-[2] sm:leading-[1.8] drop-shadow-lg px-2 break-words ${isBurmese ? 'text-lg sm:text-xl md:text-2xl' : 'text-2xl sm:text-3xl md:text-4xl'}`}>
        {t('heroTitle')}
      </h1>

      <p className={`max-w-3xl mx-auto text-gray-300 leading-relaxed px-2 sm:px-4 ${isBurmese ? 'text-base sm:text-lg' : 'text-sm sm:text-base md:text-lg'}`}>
        {t('heroDesc')}
      </p>

      <div className="mt-8 flex flex-col sm:flex-row gap-4 justify-center">
        {isRecording ? (
          <button
            onClick={stopRecording}
            className="bg-red-500 px-8 py-3 rounded-2xl text-lg hover:bg-red-600 transition"
          >
            {t('stopListening')}
          </button>
        ) : (
          <button
            onClick={startRecording}
            className="bg-green-500 px-8 py-3 rounded-2xl text-lg hover:bg-green-600 transition"
          >
            {t('startMonitoring')}
          </button>
        )}
        <button
          onClick={() => router.push('/trusted-group')}
          className="bg-blue-600 px-8 py-3 rounded-2xl text-lg hover:bg-blue-700 transition"
        >
          {t('trustedGroup')}
        </button>
      </div>

      {isRecording && (
        <div className="mt-4 text-green-400 font-mono text-lg">
          {t('monitoring')}
        </div>
      )}

      {error && (
        <div className="mt-4 text-red-400 text-sm">
          {error}
        </div>
      )}
    </section>
  )
}
