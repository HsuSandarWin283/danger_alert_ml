'use client'

import { useAuth } from '@/app/auth-provider'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import { logout } from '@/app/lib/auth'
import Navbar from './components/Navbar'
import HeroSection from './components/HeroSection'
import StatusCard from './components/StatusCard'
import DangerAlert from './components/DangerAlert'
import AudioVisualizer from './components/AudioVisualizer.jsx'
import Footer from './components/Footer'

export default function Home() {
  const { user, loading } = useAuth()
  const router = useRouter()

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
        <StatusCard />
        <DangerAlert />
      </div>
      <AudioVisualizer />
      <Footer />
    </main>
  )
}
