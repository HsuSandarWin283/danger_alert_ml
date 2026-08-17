"use client"

import { useRouter } from 'next/navigation'
import { useMicrophoneContext } from "@/app/lib/MicrophoneProvider"
import { useLang } from "@/app/lib/LanguageProvider"

export default function HeroSection() {
  const router = useRouter()
  const { isRecording, recordingTime, startRecording, stopRecording, error } = useMicrophoneContext()
  const { t } = useLang()

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
  }

  return (
    <section className="text-center py-16 px-6 bg-gradient-to-r from-black to-gray-800 text-white">
      <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold mb-6 leading-[1.75] drop-shadow-lg">
        {t('heroTitle')}
      </h1>

      <p className="text-base sm:text-lg max-w-3xl mx-auto text-gray-300 leading-relaxed">
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
