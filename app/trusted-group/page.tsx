'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '@/app/auth-provider'
import { useRouter } from 'next/navigation'
import { searchUsersOnce, addMemberToGroup, removeMemberFromGroup, getUserById, getGroupMembers } from '@/app/lib/trusted-group'
import { SearchResult, User } from '@/app/lib/trusted-group-types'
import UserCard from '@/app/components/trusted-group/UserCard'
import MemberCard from '@/app/components/trusted-group/MemberCard'
import SearchBar from '@/app/components/trusted-group/SearchBar'

export default function TrustedGroupPage() {
  const { user, loading: authLoading } = useAuth()
  const router = useRouter()
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [groupMembers, setGroupMembers] = useState<(User & { joinedAt: Date })[]>([])
  const [addingUserId, setAddingUserId] = useState<string | null>(null)
  const [removingUserId, setRemovingUserId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace('/login')
    }
  }, [user, authLoading, router])

  useEffect(() => {
    if (!user) return

    const fetchResults = async () => {
      setLoading(true)
      try {
        const results = await searchUsersOnce(searchQuery, user.uid)
        setSearchResults(results)
      } catch (err) {
        console.error('Error searching users:', err)
      } finally {
        setLoading(false)
      }
    }

    const debounceTimer = setTimeout(fetchResults, 300)
    return () => clearTimeout(debounceTimer)
  }, [searchQuery, user])

  useEffect(() => {
    if (!user) return

    const unsubscribe = getGroupMembers(user.uid, async (memberRefs) => {
      const memberData = await Promise.all(
        memberRefs.map(async (m) => {
          const u = await getUserById(m.userId)
          return u ? { ...u, joinedAt: m.joinedAt } : null
        })
      )
      setGroupMembers(memberData.filter((m): m is User & { joinedAt: Date } => m !== null))
      setInitialLoading(false)
    })

    return () => unsubscribe()
  }, [user])

  const handleAddMember = async (userId: string) => {
    setAddingUserId(userId)
    if (!user) return
    try {
      await addMemberToGroup(user.uid, userId)
      const results = await searchUsersOnce(searchQuery, user.uid)
      setSearchResults(results)
    } catch (error) {
      console.error('Error adding member:', error)
    } finally {
      setAddingUserId(null)
    }
  }

  const handleRemoveMember = async (userId: string) => {
    setRemovingUserId(userId)
    if (!user) return
    try {
      await removeMemberFromGroup(user.uid, userId)
      const results = await searchUsersOnce(searchQuery, user.uid)
      setSearchResults(results)
    } catch (error) {
      console.error('Error removing member:', error)
    } finally {
      setRemovingUserId(null)
    }
  }

  if (authLoading || initialLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="text-center">
          <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-600">Loading trusted group...</p>
        </div>
      </div>
    )
  }

  if (!user) return null

  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-black text-white px-6 py-4 flex justify-between items-center">
        <h1 className="text-2xl font-bold">AI Safety Companion</h1>
        <button
          onClick={() => {
            router.push('/')
          }}
          className="px-4 py-2 bg-gray-800 rounded-xl hover:bg-gray-700 transition"
        >
          Back to Dashboard
        </button>
      </nav>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        <h2 className="text-3xl font-bold text-gray-800 mb-2">Trusted Group Management</h2>
        <p className="text-gray-600 mb-6">Manage your trusted contacts for emergency alerts</p>

        <div className="mb-8">
          <h3 className="text-xl font-semibold text-gray-700 mb-4">Search & Add Users</h3>
          <div className="max-w-xl mb-4">
            <SearchBar value={searchQuery} onChange={setSearchQuery} />
          </div>

          <div className="space-y-3">
            {loading ? (
              <div className="text-center py-8">
                <div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full mx-auto mb-2"></div>
                <p className="text-gray-500">Searching users...</p>
              </div>
            ) : searchQuery && searchResults.length === 0 ? (
              <div className="bg-white rounded-2xl p-8 text-center">
                <p className="text-gray-500">No users found matching your search</p>
              </div>
            ) : (
              searchResults.map((u) => (
                <UserCard
                  key={u.uid}
                  user={u}
                  onAdd={handleAddMember}
                  adding={addingUserId === u.uid}
                />
              ))
            )}

            {!searchQuery && searchResults.length === 0 && !loading && (
              <div className="bg-white rounded-2xl p-8 text-center">
                <p className="text-gray-500">Start typing to search for users</p>
              </div>
            )}
          </div>
        </div>

        <div>
          <h3 className="text-xl font-semibold text-gray-700 mb-4">
            Current Group Members ({groupMembers.length})
          </h3>

          <div className="space-y-3">
            {groupMembers.length === 0 ? (
              <div className="bg-white rounded-2xl p-8 text-center">
                <svg
                  className="w-12 h-12 text-gray-300 mx-auto mb-3"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 4.354a4 4 0 110 5.292 7.002 7.002 0 0015.622-2.994 7.002 7.002 0 00-2.994-5.622 7.002 7.002 0 00-5.622 2.994 7.002 7.002 0 00-2.994 5.622A4 4 0 0112 4.354z"
                  />
                </svg>
                <p className="text-gray-500">No members in your trusted group yet</p>
              </div>
            ) : (
              groupMembers.map((m) => (
                <MemberCard
                  key={m.uid}
                  member={m}
                  onRemove={handleRemoveMember}
                  removing={removingUserId === m.uid}
                />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}