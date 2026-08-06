'use client'

import { useState, useEffect, FormEvent, useRef } from 'react'
import { useAuth } from '@/app/auth-provider'
import { useRouter } from 'next/navigation'
import { doc, getDoc, setDoc } from 'firebase/firestore'
import { db } from '@/app/lib/firebase'
import Navbar from '@/app/components/Navbar'
import { useLang } from '@/app/lib/LanguageProvider'
import { uploadToCloudinary } from '@/app/lib/cloudinary'

type ProfileForm = {
  name: string
  email: string
  phone: string
  photoURL: string
}

const DEFAULT_PROFILE: ProfileForm = {
  name: '',
  email: '',
  phone: '',
  photoURL: '',
}

export default function ProfilePage() {
  const { user, loading: authLoading } = useAuth()
  const router = useRouter()
  const { t } = useLang()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [form, setForm] = useState<ProfileForm>(DEFAULT_PROFILE)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
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
      if (!cancelled) {
        const fallbackName = user.displayName || user.email?.split('@')[0] || ''
        const fallbackPhoto = user.photoURL || ''
        if (snap.exists()) {
          const data = snap.data()
          setForm({
            name: data.name || fallbackName,
            email: data.email || user.email || '',
            phone: data.phone || '',
            photoURL: data.photoURL || fallbackPhoto,
          })
        } else {
          setForm({
            name: fallbackName,
            email: user.email || '',
            phone: '',
            photoURL: fallbackPhoto,
          })
        }
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [user])

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !user) return

    if (file.size > 5 * 1024 * 1024) {
      setMessage(t('imageTooLarge'))
      return
    }

    setUploading(true)
    setMessage(null)
    try {
      const url = await uploadToCloudinary(file)
      setForm((prev) => ({ ...prev, photoURL: url }))
      await setDoc(doc(db, 'users', user.uid), { photoURL: url }, { merge: true })
      setMessage(t('imageUploaded'))
    } catch (err) {
      console.error('Image upload failed', err)
      setMessage(t('imageUploadFailed'))
    } finally {
      setUploading(false)
    }
  }

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
          photoURL: form.photoURL || null,
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

  const avatarUrl = form.photoURL || `https://ui-avatars.com/api/?name=${encodeURIComponent(form.name || form.email)}&background=3b82f6&color=fff&size=128`

  return (
    <div className="min-h-screen bg-gray-100">
      <Navbar userEmail={user.email} showBack onBack={() => router.back()} onLogout={() => {}} />

      <div className="max-w-2xl mx-auto px-6 py-10">
        <h2 className="text-3xl font-bold text-gray-800 mb-2">{t('editProfile')}</h2>
        <p className="text-gray-600 mb-6">{t('updateProfileDesc')}</p>

        <div className="bg-white rounded-3xl shadow-lg p-8 space-y-6">
          <div className="flex flex-col items-center gap-4">
            <div className="relative group cursor-pointer" onClick={() => fileInputRef.current?.click()}>
              <img
                src={avatarUrl}
                alt={form.name || 'Profile'}
                className="w-28 h-28 rounded-full object-cover border-4 border-gray-200 group-hover:opacity-80 transition"
                onError={(e) => {
                  e.currentTarget.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(form.name || form.email)}&background=3b82f6&color=fff&size=128`
                }}
              />
              <div className="absolute inset-0 rounded-full bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition">
                <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 0 01.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </div>
              {uploading && (
                <div className="absolute inset-0 rounded-full bg-black/40 flex items-center justify-center">
                  <div className="animate-spin w-8 h-8 border-3 border-white border-t-transparent rounded-full"></div>
                </div>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleImageUpload}
              className="hidden"
            />
            <p className="text-sm text-gray-500">{t('tapToChangePhoto')}</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
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
    </div>
  )
}
