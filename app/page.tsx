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
      <Navbar userEmail={user.email} onLogout={handleLogout} showBack={false} onBack={() => {}} />
      <HeroSection />
      <div className="max-w-6xl mx-auto px-6 py-10 grid md:grid-cols-2 gap-6">
        <StatusCard error={error} />
        <DangerAlert
          detectedAnswer={lastDanger?.detectedAnswer}
          confidence={lastDanger?.confidence}
        />
      </div>

      <AudioVisualizer />
      <Footer />
    </main>
  )
}
