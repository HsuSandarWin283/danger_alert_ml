'use client'

import { useState, useEffect, FormEvent } from 'react'
import { useAuth } from '@/app/auth-provider'
import { useRouter } from 'next/navigation'
import { doc, getDoc, setDoc } from 'firebase/firestore'
import { db } from '@/app/lib/firebase'
import Navbar from '@/app/components/Navbar'
import { useLang } from '@/app/lib/LanguageProvider'

const DEFAULT_PROFILE = {
  name: '',
  email: '',
  phone: '',
}

export default function ProfilePage() {
  const { user, loading: authLoading } = useAuth()
  const router = useRouter()
  const { t } = useLang()
  const [form, setForm] = useState(DEFAULT_PROFILE)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace('/login')
    }
  }, [user, authLoading, router])

  useEffect(() => {
    if (!user) return
    let cancelled = false
    const load = async () => {
      const ref = doc(db, 'users', user.uid)
      const snap = await getDoc(ref)
      if (!cancelled && snap.exists()) {
        const data = snap.data()
        setForm({
          name: data.name || '',
          email: data.email || user.email || '',
          phone: data.phone || '',
        })
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [user])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!user) return
    setSaving(true)
    setMessage(null)
    try {
      const ref = doc(db, 'users', user.uid)
      await setDoc(
        ref,
        {
          uid: user.uid,
          email: form.email,
          name: form.name,
          phone: form.phone || null,
        },
        { merge: true }
      )
      setMessage(t('profileUpdated'))
    } catch (err) {
      console.error('Profile update failed', err)
      setMessage(t('profileUpdateFailed'))
    } finally {
      setSaving(false)
    }
  }

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <p className="text-gray-600">{t('loading')}</p>
      </div>
    )
  }

  if (!user) return null

  return (
    <div className="min-h-screen bg-gray-100">
      <Navbar userEmail={user.email} showBack onBack={() => router.push('/settings')} onLogout={() => {}} />

      <div className="max-w-2xl mx-auto px-6 py-10">
        <h2 className="text-3xl font-bold text-gray-800 mb-2">{t('editProfile')}</h2>
        <p className="text-gray-600 mb-6">{t('updateProfileDesc')}</p>

        <form onSubmit={handleSubmit} className="bg-white rounded-3xl shadow-lg p-8 space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('name')}</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full rounded-xl border border-gray-300 p-3"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('email')}</label>
            <input
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              type="email"
              className="w-full rounded-xl border border-gray-300 p-3"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('phone')}</label>
            <input
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              className="w-full rounded-xl border border-gray-300 p-3"
            />
          </div>

          <button
            type="submit"
            disabled={saving}
            className="w-full py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition disabled:opacity-50"
          >
            {saving ? t('saving') : t('saveProfile')}
          </button>

          {message && <p className="text-sm text-gray-600 text-center">{message}</p>}
        </form>
      </div>
    </div>
  )
}
