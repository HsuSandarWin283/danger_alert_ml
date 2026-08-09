'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Capacitor } from '@capacitor/core'

export default function PendingNavigate() {
  const router = useRouter()

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return

    const handler = (e: Event) => {
      const route = (e as CustomEvent).detail?.route
      if (route) {
        console.log('[PendingNavigate] Navigating to:', route)
        router.push(route)
      }
    }

    window.addEventListener('capacitor-navigate', handler)
    return () => window.removeEventListener('capacitor-navigate', handler)
  }, [router])

  return null
}
