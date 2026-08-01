'use client'

import Link from 'next/link'
import LoginForm from '@/app/ui/login-form'
import { useLang } from '@/app/lib/LanguageProvider'

export default function LoginContent() {
  const { t } = useLang()

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h1 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            {t('loginTitle')}
          </h1>
          <p className="mt-2 text-center text-sm text-gray-600">
            {t('loginDesc')}
          </p>
        </div>
        <div className="mt-8 bg-white py-8 px-6 shadow-lg rounded-lg">
          <LoginForm />
        </div>
        <p className="text-center text-sm text-gray-600">
          {t('noAccount')}{' '}
          <Link href="/signup" className="font-medium text-blue-600 hover:text-blue-500">
            {t('signUp')}
          </Link>
        </p>
      </div>
    </div>
  )
}
