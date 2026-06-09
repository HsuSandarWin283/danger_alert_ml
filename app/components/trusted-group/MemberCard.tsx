'use client'

import { User } from '@/app/lib/trusted-group-types'

interface MemberCardProps {
  member: User & { joinedAt: Date }
  onRemove: (userId: string) => void
  removing: boolean
}

export default function MemberCard({ member, onRemove, removing }: MemberCardProps) {
  return (
    <div className="bg-white rounded-2xl shadow-md p-4 flex items-center gap-4 hover:shadow-lg transition">
      <img
        src={member.photoURL || `https://ui-avatars.com/api/?name=${encodeURIComponent(member.name || member.email)}&background=random`}
        alt={member.name}
        className="w-12 h-12 rounded-full object-cover"
        onError={(e) => {
          e.currentTarget.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(member.name || member.email)}&background=random`
        }}
      />
      <div className="flex-1 min-w-0">
        <h3 className="font-semibold text-gray-800 truncate">{member.name || 'Unnamed User'}</h3>
        <p className="text-sm text-gray-500 truncate">{member.email}</p>
        <p className="text-xs text-gray-400 mt-1">
          Joined {new Date(member.joinedAt).toLocaleDateString()}
        </p>
      </div>
      <button
        onClick={() => onRemove(member.uid)}
        disabled={removing}
        className="px-4 py-2 bg-red-100 text-red-700 rounded-xl hover:bg-red-200 disabled:opacity-50 transition"
      >
        {removing ? 'Removing...' : 'Remove'}
      </button>
    </div>
  )
}