'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '@/app/auth-provider'
import { useRouter } from 'next/navigation'
import { getHelpHistoryForUser, type HelpMessage } from '@/app/lib/help-history'

export default function HelpHistoryPage() {
  const { user, loading: authLoading } = useAuth()
  const router = useRouter()
  const [items, setItems] = useState<HelpMessage[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace('/login')
    }
  }, [user, authLoading, router])

  useEffect(() => {
    if (!user) return
    let cancelled = false
    const load = async () => {
      setLoading(true)
      try {
        const data = await getHelpHistoryForUser(user.uid)
        if (!cancelled) setItems(data)
      } catch (err) {
        console.error('Failed to load help history', err)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [user])

  if (authLoading || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <p className="text-gray-600">Loading help history...</p>
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

      <div className="max-w-4xl mx-auto px-6 py-10">
        <h2 className="text-3xl font-bold text-gray-800 mb-2">Help History</h2>
        <p className="text-gray-600 mb-6">Alerts sent by you or received from your trusted group</p>

        {items.length === 0 ? (
          <div className="bg-white rounded-3xl shadow-lg p-10 text-center">
            <p className="text-gray-500">No help alerts yet.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {items.map((item) => {
              const isSender = item.senderId === user.uid
              return (
                <div key={item.id} className="bg-white rounded-3xl shadow-lg p-6">
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <h3 className="text-xl font-bold text-gray-900">
                        {item.dangerType ? `Danger: ${item.dangerType.toUpperCase()}` : 'Help Request'}
                      </h3>
                      <p className="text-sm text-gray-500">
                        {item.createdAt ? new Date(item.createdAt).toLocaleString() : ''}
                      </p>
                      <p className="text-xs text-gray-400 mt-1">
                        {isSender ? `To: ${item.receiverIds?.length ?? 0} member(s)` : `From: ${item.senderName || item.senderId}`}
                      </p>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-xs font-semibold uppercase ${
                      isSender ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                    }`}>
                      {isSender ? 'Sent' : 'Received'}
                    </span>
                  </div>
                  <p className="text-gray-700 whitespace-pre-line">{item.alertMsg}</p>
                  {(item.lat !== undefined && item.lng !== undefined) && (
                    <p className="text-sm text-gray-500 mt-2">
                      Location: {item.locationName || `${item.lat.toFixed(4)}, ${item.lng.toFixed(4)}`}
                    </p>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
