'use client'

import { useEffect } from 'react'
import { useAuth } from '@/app/auth-provider'
import { useRouter } from 'next/navigation'
import { logout } from '@/app/lib/auth'
import { useLang } from '@/app/lib/LanguageProvider'
import LanguageSwitch from '@/app/components/LanguageSwitch'
import Navbar from '@/app/components/Navbar'

export default function SettingsPage() {
  const { user, loading: authLoading } = useAuth()
  const router = useRouter()
  const { t } = useLang()

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace('/login')
    }
  }, [user, authLoading, router])

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <p className="text-gray-600">{t('loading')}</p>
      </div>
    )
  }

  if (!user) return null

  const handleLogout = async () => {
    if (window.confirm(t('logoutConfirm'))) {
      await logout()
      router.replace('/login')
      router.refresh()
    }
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <Navbar userEmail={user.email} showBack onBack={() => router.push('/')} onLogout={() => {}} />

      <div className="max-w-2xl mx-auto px-6 py-10">
        <h2 className="text-3xl font-bold text-gray-800 mb-6">{t('settings')}</h2>

        <div className="bg-white rounded-3xl shadow-lg overflow-hidden">
          {/* Language */}
          <div className="flex items-center justify-between p-5 border-b border-gray-100">
            <span className="text-lg font-medium text-gray-800">{t('language')}</span>
            <LanguageSwitch />
          </div>

          {/* Help History */}
          <button
            onClick={() => router.push('/help-history')}
            className="w-full flex items-center justify-between p-5 border-b border-gray-100 hover:bg-gray-50 transition text-left"
          >
            <span className="text-lg font-medium text-gray-800">{t('helpHistory')}</span>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-gray-400">
              <path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z" />
            </svg>
          </button>

          {/* Profile */}
          <button
            onClick={() => router.push('/profile')}
            className="w-full flex items-center justify-between p-5 border-b border-gray-100 hover:bg-gray-50 transition text-left"
          >
            <span className="text-lg font-medium text-gray-800">{t('profile')}</span>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-gray-400">
              <path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z" />
            </svg>
          </button>

          {/* Logout */}
          <button
            onClick={handleLogout}
            className="w-full flex items-center justify-between p-5 hover:bg-red-50 transition text-left"
          >
            <span className="text-lg font-medium text-red-600">{t('logout')}</span>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-red-500">
              <path d="M10.09 15.59 11.5 17l5-5-5-5-1.41 1.41L12.67 11H3v2h9.67l-2.58 2.59zM19 3H5a2 2 0 0 0-2 2v4h2V5h14v14H5v-4H3v4a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
