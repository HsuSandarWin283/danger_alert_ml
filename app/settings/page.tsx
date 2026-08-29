'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@/app/auth-provider'
import { useRouter } from 'next/navigation'
import { logout } from '@/app/lib/auth'
import { deleteDoc, doc, collection, query, where, getDocs } from 'firebase/firestore'
import { reauthenticateWithCredential, EmailAuthProvider, deleteUser } from 'firebase/auth'
import { db } from '@/app/lib/firebase'
import { useLang } from '@/app/lib/LanguageProvider'
import LanguageSwitch from '@/app/components/LanguageSwitch'
import Navbar from '@/app/components/Navbar'

export default function SettingsPage() {
  const { user, loading: authLoading } = useAuth()
  const router = useRouter()
  const { t } = useLang()
  const [deleting, setDeleting] = useState(false)
  const [showConfirmModal, setShowConfirmModal] = useState(false)
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const [password, setPassword] = useState('')
  const [passwordError, setPasswordError] = useState('')

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace('/login')
    }
  }, [user, authLoading, router])

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <p className="text-gray-600" suppressHydrationWarning>{t('loading')}</p>
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

  const handleDeleteAccount = async () => {
    if (!user) return
    setShowConfirmModal(true)
  }

  const proceedToPassword = () => {
    setShowConfirmModal(false)
    setShowPasswordModal(true)
    setPassword('')
    setPasswordError('')
  }

  const confirmDelete = async () => {
    if (!user || !password) {
      setPasswordError(t('deletePasswordRequired'))
      return
    }
    setDeleting(true)
    setPasswordError('')
    try {
      const credential = EmailAuthProvider.credential(user.email || '', password)
      await reauthenticateWithCredential(user, credential)
    } catch (err) {
      console.error('Reauthentication failed', err)
      setPasswordError(t('deleteInvalidPassword'))
      setDeleting(false)
      return
    }
    try {
      const ownedQuery = query(collection(db, 'group_members'), where('groupId', '==', user.uid))
      const memberQuery = query(collection(db, 'group_members'), where('userId', '==', user.uid))
      const [ownedSnap, memberSnap] = await Promise.all([getDocs(ownedQuery), getDocs(memberQuery)])
      const ownedDeletes = ownedSnap.docs.map((d) => deleteDoc(d.ref))
      const memberDeletes = memberSnap.docs.map((d) => deleteDoc(d.ref))
      await Promise.all([...ownedDeletes, ...memberDeletes])
    } catch (err) {
      console.error('Failed to delete group members', err)
      alert('Failed to delete group members. Please try again.')
      setDeleting(false)
      return
    }
    try {
      await deleteDoc(doc(db, 'users', user.uid))
    } catch (err) {
      console.error('Failed to delete user profile from Firestore', err)
      alert('Failed to delete profile data. Please try again.')
      setDeleting(false)
      return
    }
    try {
      await deleteUser(user)
    } catch (err) {
      console.error('Failed to delete Firebase Auth user', err)
      alert('Account deletion failed. Please try again.')
      setDeleting(false)
      return
    }
    setShowPasswordModal(false)
    router.replace('/login')
    router.refresh()
  }

  const cancelDelete = () => {
    setShowPasswordModal(false)
    setPassword('')
    setPasswordError('')
    setDeleting(false)
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

          {/* Delete Account */}
          <button
            onClick={handleDeleteAccount}
            disabled={deleting}
            className="w-full flex items-center justify-between p-5 hover:bg-red-50 transition text-left disabled:opacity-50"
          >
            <span className="text-lg font-medium text-red-600">{deleting ? t('deleting') : t('deleteAcc')}</span>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-red-500">
              <path d="M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" />
            </svg>
          </button>
        </div>
      </div>

      {showConfirmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-sm w-full">
            <div className="text-center mb-6">
              <div className="text-5xl mb-4">⚠️</div>
              <h3 className="text-2xl font-bold text-gray-900 mb-2">{t('deleteAccountTitle')}</h3>
              <p className="text-gray-600">{t('deleteAccountDesc')}</p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setShowConfirmModal(false)}
                disabled={deleting}
                className="flex-1 bg-gray-200 text-gray-800 py-3 rounded-xl text-lg font-semibold hover:bg-gray-300 transition disabled:opacity-50"
              >
                {t('cancel')}
              </button>
              <button
                onClick={proceedToPassword}
                disabled={deleting}
                className="flex-1 bg-red-600 text-white py-3 rounded-xl text-lg font-semibold hover:bg-red-700 transition disabled:opacity-50"
              >
                {t('continue')}
              </button>
            </div>
          </div>
        </div>
      )}

      {showPasswordModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-sm w-full">
            <div className="flex justify-end mb-2">
              <button
                onClick={cancelDelete}
                disabled={deleting}
                className="text-gray-400 hover:text-gray-600 text-2xl font-bold w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-100 transition"
              >
                ×
              </button>
            </div>

            <div className="text-center mb-6">
              <div className="text-5xl mb-4">🔒</div>
              <h3 className="text-2xl font-bold text-gray-900 mb-2">{t('deleteConfirmTitle')}</h3>
              <p className="text-gray-600">{t('deleteConfirmDesc')}</p>
            </div>

            <div className="space-y-4">
              <div>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    setPasswordError('')
                  }}
                  placeholder={t('deletePasswordPlaceholder')}
                  className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-red-500 focus:outline-none text-gray-800"
                />
                {passwordError && (
                  <p className="text-red-500 text-sm mt-2 text-center">{passwordError}</p>
                )}
              </div>

              <button
                onClick={confirmDelete}
                disabled={deleting}
                className="w-full bg-red-600 text-white py-3 rounded-xl text-lg font-semibold hover:bg-red-700 transition disabled:opacity-50"
              >
                {deleting ? t('deleting') : t('deleteAcc')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
