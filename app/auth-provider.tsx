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
        firebaseUser.getIdToken().then((token) => {
          import('@/app/lib/background-monitor').then(({ default: BackgroundMonitor }) => {
            BackgroundMonitor.saveFirebaseConfig({
              apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY || '',
              projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || '',
              userId: firebaseUser.uid,
              authToken: token,
              phone: '',
              fcmToken: '',
              serverKey: '',
              clientEmail: '',
              privateKey: '',
            })

            BackgroundMonitor.fetchFcmToken({ userId: firebaseUser.uid }).then(({ fcmToken }) => {
              if (fcmToken) {
                import('firebase/firestore').then(({ doc, setDoc, getFirestore }) => {
                  const db = getFirestore()
                  setDoc(doc(db, 'users', firebaseUser.uid), { fcmToken }, { merge: true })
                    .then(() => console.log('[AuthProvider] FCM token saved to Firestore via JS SDK'))
                    .catch((e) => console.error('[AuthProvider] Firestore save failed:', e.message))
                })
              } else {
                console.error('[AuthProvider] fetchFcmToken returned empty token')
              }
            }).catch((e) => console.error('[AuthProvider] fetchFcmToken failed:', e.message))
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
