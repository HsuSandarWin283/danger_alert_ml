'use client'

import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '@/app/auth-provider'
import { useRouter } from 'next/navigation'
import { logout } from '@/app/lib/auth'
import { useDangerSoundMonitor, type DangerAlertPayload } from '@/app/lib/useDangerSoundMonitor'
import Navbar from './components/Navbar'
import HeroSection from './components/HeroSection'
import StatusCard from './components/StatusCard'
import DangerAlert from './components/DangerAlert'
import AudioVisualizer from './components/AudioVisualizer.jsx'
import Footer from './components/Footer'

type LastDangerState = Pick<DangerAlertPayload, 'detectedAnswer' | 'confidence'>

export default function Home() {
  const { user, loading } = useAuth()
  const router = useRouter()
  const [lastDanger, setLastDanger] = useState<LastDangerState | null>(null)

  const handleDangerDetected = useCallback((payload: DangerAlertPayload) => {
    setLastDanger(payload)
  }, [])

  const {
    isMonitoring,
    isRecording,
    rmsLevel,
    lastPrediction,
    error,
    startMonitoring,
    stopMonitoring,
  } = useDangerSoundMonitor(handleDangerDetected)

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login')
    }
  }, [user, loading, router])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <p className="text-gray-600">Loading...</p>
      </div>
    )
  }

  if (!user) return null

  const handleLogout = async () => {
    await logout()
    router.replace('/login')
    router.refresh()
  }

  return (
    <main className="bg-gray-100 min-h-screen">
      <Navbar userEmail={user.email} onLogout={handleLogout} />
      <HeroSection />
      <div className="max-w-6xl mx-auto px-6 py-10 grid md:grid-cols-2 gap-6">
        <StatusCard error={error} />
        <DangerAlert
          detectedAnswer={lastDanger?.detectedAnswer}
          confidence={lastDanger?.confidence}
        />
      </div>

      {/* <section className="max-w-6xl mx-auto px-6 py-6">
        <div className="bg-white rounded-3xl shadow-lg p-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
            <div>
              <h2 className="text-3xl font-bold">
                Real-time Microphone Monitor
              </h2>
              <p className="text-gray-600 mt-2">
                {isMonitoring
                  ? 'Listening for danger sounds. Meaningful audio is sent to /predict.'
                  : 'Start monitoring to listen for gunshot, scream, or glass break sounds.'}
              </p>
            </div>

            <button
              type="button"
              onClick={isMonitoring ? stopMonitoring : startMonitoring}
              className={`px-6 py-3 rounded-xl text-white font-semibold transition disabled:opacity-50
                ${isMonitoring ? 'bg-red-500 hover:bg-red-600' : 'bg-green-600 hover:bg-green-700'}`}
            >
              {isMonitoring ? 'Stop Monitoring' : 'Start Monitoring'}
            </button>
          </div>

          <div className="grid md:grid-cols-3 gap-4">
            <div className="bg-gray-50 rounded-2xl p-4">
              <p className="text-sm text-gray-500">Status</p>
              <p className="text-xl font-bold text-gray-900">
                {isRecording ? 'Recording' : 'Stopped'}
              </p>
            </div>

            <div className="bg-gray-50 rounded-2xl p-4">
              <p className="text-sm text-gray-500">RMS Level</p>
              <p className="text-xl font-bold text-gray-900">
                {rmsLevel.toFixed(4)}
              </p>
            </div>

            <div className="bg-gray-50 rounded-2xl p-4">
              <p className="text-sm text-gray-500">Last Prediction</p>
              <p className="text-xl font-bold text-gray-900">
                {lastPrediction
                  ? `${lastPrediction.prediction} (${Math.round(lastPrediction.confidence * 100)}%)`
                  : 'None'}
              </p>
            </div>
          </div>

          {error && (
            <div className="mt-4 bg-red-50 text-red-700 rounded-xl p-4">
              {error}
            </div>
          )}
        </div>
      </section> */}

      <AudioVisualizer />
      <Footer />
    </main>
  )
}
