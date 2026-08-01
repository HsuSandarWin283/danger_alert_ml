'use client'

import { useState } from 'react'
import { signupWithEmail } from '@/app/lib/auth'
import { createUserProfile } from '@/app/lib/user-profile'
import { useRouter } from 'next/navigation'
import { useLang } from '@/app/lib/LanguageProvider'

export default function SignupForm() {
  const router = useRouter()
  const { t } = useLang()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const user = await signupWithEmail(email, password)
      if (user) {
        await createUserProfile(user.uid, name, email, phone)
      }
      router.push('/')
      router.refresh()
    } catch (err) {
      const message = err instanceof Error ? err.message : t('signupFailed')
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="mb-4">
        <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
          {t('name')}
        </label>
        <input
          id="name"
          name="name"
          type="text"
          placeholder={t('name')}
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-green-500 focus:border-transparent"
          required
          autoComplete="name"
        />
      </div>

      <div className="mb-4">
        <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
          {t('email')}
        </label>
        <input
          id="email"
          name="email"
          type="email"
          placeholder={t('email')}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-green-500 focus:border-transparent"
          required
          autoComplete="email"
        />
      </div>

      <div className="mb-4">
        <label htmlFor="phone" className="block text-sm font-medium text-gray-700 mb-1">
          {t('phoneNumber')}
        </label>
        <input
          id="phone"
          name="phone"
          type="tel"
          placeholder="+959xxxxxxxxx"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-green-500 focus:border-transparent"
          required
          autoComplete="tel"
        />
      </div>

      <div className="mb-6">
        <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
          {t('password')}
        </label>
        <input
          id="password"
          name="password"
          type="password"
          placeholder={t('password')}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-green-500 focus:border-transparent"
          required
          autoComplete="new-password"
        />
      </div>

      {error && <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">{error}</div>}

      <button
        type="submit"
        disabled={loading}
        className="w-full bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700 disabled:opacity-50"
      >
        {loading ? t('creatingAccount') : t('signUp')}
      </button>
    </form>
  )
}
