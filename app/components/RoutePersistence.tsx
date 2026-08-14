'use client'

import { useEffect, useRef } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { useAuth } from '@/app/auth-provider'

export default function RoutePersistence() {
  const pathname = usePathname()
  const router = useRouter()
  const { user, loading } = useAuth()
  const restored = useRef(false)

  useEffect(() => {
    if (!loading && user && !restored.current) {
      restored.current = true
      const lastRoute = sessionStorage.getItem('last_route')
      if (lastRoute && lastRoute !== pathname && lastRoute !== '/login') {
        router.replace(lastRoute)
      }
    }
  }, [loading, user, pathname, router])

  useEffect(() => {
    if (!loading && user) {
      sessionStorage.setItem('last_route', pathname)
    }
  }, [pathname, user, loading])

  return null
}
