'use client'

import { useState, useEffect, FormEvent } from 'react'
import { useAuth } from '@/app/auth-provider'
import { useRouter } from 'next/navigation'
import { doc, getDoc, setDoc } from 'firebase/firestore'
import { db } from '@/app/lib/firebase'

const DEFAULT_PROFILE = {
  name: '',
  phone: '',
  photoURL: '',
}

export default function ProfilePage() {
  const { user, loading: authLoading } = useAuth()
  const router = useRouter()
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
          phone: data.phone || '',
          photoURL: data.photoURL || '',
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
          email: user.email,
          name: form.name,
          phone: form.phone || null,
          photoURL: form.photoURL || null,
        },
        { merge: true }
      )
      setMessage('Profile updated')
    } catch (err) {
      console.error('Profile update failed', err)
      setMessage('Failed to update profile')
    } finally {
      setSaving(false)
    }
  }

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <p className="text-gray-600">Loading...</p>
      </div>
    )
  }

  if (!user) return null

  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-black text-white px-6 py-4 flex justify-between items-center">
        <h1 className="text-2xl font-bold">AI Safety Companion</h1>
        <button
          onClick={() => router.push('/')}
          className="px-4 py-2 bg-gray-800 rounded-xl hover:bg-gray-700 transition"
        >
          Back to Dashboard
        </button>
      </nav>

      <div className="max-w-2xl mx-auto px-6 py-10">
        <h2 className="text-3xl font-bold text-gray-800 mb-2">Edit Profile</h2>
        <p className="text-gray-600 mb-6">Update your personal information</p>

        <form onSubmit={handleSubmit} className="bg-white rounded-3xl shadow-lg p-8 space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full rounded-xl border border-gray-300 p-3"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              value={user.email || ''}
              className="w-full rounded-xl border border-gray-300 p-3 bg-gray-100"
              disabled
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
            <input
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              className="w-full rounded-xl border border-gray-300 p-3"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Photo URL</label>
            <input
              value={form.photoURL}
              onChange={(e) => setForm({ ...form, photoURL: e.target.value })}
              className="w-full rounded-xl border border-gray-300 p-3"
              placeholder="https://..."
            />
          </div>

          <button
            type="submit"
            disabled={saving}
            className="w-full py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Profile'}
          </button>

          {message && <p className="text-sm text-gray-600 text-center">{message}</p>}
        </form>
      </div>
    </div>
  )
}
