'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import { User } from 'firebase/auth'
import { listenToAuth } from '@/app/lib/auth'
import { Capacitor } from '@capacitor/core'

type AuthContextValue = {
  user: User | null
  loading: boolean
}

const AuthContext = createContext<AuthContextValue>({ user: null, loading: true })

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const unsubscribe = listenToAuth((firebaseUser) => {
      setUser(firebaseUser)
      setLoading(false)

      if (firebaseUser && Capacitor.isNativePlatform()) {
        import('@/app/lib/background-monitor').then(({ default: BackgroundMonitor }) => {
          BackgroundMonitor.saveFirebaseConfig({
            apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY || '',
            projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || '',
            userId: firebaseUser.uid,
          })
        })
      }
    })
    return () => unsubscribe()
  }, [])

  return <AuthContext.Provider value={{ user, loading }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}
