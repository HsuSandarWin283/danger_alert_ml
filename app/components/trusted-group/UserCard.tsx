'use client'

import { SearchResult } from '@/app/lib/trusted-group-types'
import { useLang } from '@/app/lib/LanguageProvider'

interface UserCardProps {
  user: SearchResult
  onAdd: (userId: string) => void
  adding: boolean
}

export default function UserCard({ user, onAdd, adding }: UserCardProps) {
  const { t } = useLang()

  return (
    <div className="bg-white rounded-2xl shadow-md p-4 flex items-center gap-4 hover:shadow-lg transition">
      <img
        src={user.photoURL || `https://ui-avatars.com/api/?name=${encodeURIComponent(user.name || user.email)}&background=random`}
        alt={user.name}
        className="w-12 h-12 rounded-full object-cover"
        onError={(e) => {
          e.currentTarget.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(user.name || user.email)}&background=random`
        }}
      />
      <div className="flex-1 min-w-0">
        <h3 className="font-semibold text-gray-800 truncate">{user.name || t('unnamedUser')}</h3>
        <p className="text-sm text-gray-500 truncate">{user.email}</p>
      </div>
      {user.isMember ? (
        <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium">
          {t('added')}
        </span>
      ) : (
        <button
          onClick={() => onAdd(user.uid)}
          disabled={adding}
          className="px-4 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 transition"
        >
          {adding ? t('adding') : t('add')}
        </button>
      )}
    </div>
  )
}
