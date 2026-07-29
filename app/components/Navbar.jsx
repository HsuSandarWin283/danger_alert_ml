'use client'

import { useRouter } from 'next/navigation'

export default function Navbar({ userEmail, onLogout }) {
  const router = useRouter()
  const handleLogoutClick = () => {
    if (window.confirm('Are you sure you want to logout?')) {
      onLogout()
    }
  }

  return (
    <nav className="bg-black text-white px-6 py-4 flex justify-between items-center">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">AI Safety Companion</h1>
      </div>

      {userEmail ? (
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push('/help-history')}
            className="px-4 py-2 bg-gray-800 rounded-xl hover:bg-gray-700 transition"
          >
            Help History
          </button>
          <button
            onClick={() => router.push('/profile')}
            className="px-4 py-2 bg-gray-800 rounded-xl hover:bg-gray-700 transition"
          >
            Profile
          </button>
          <span className="text-sm hidden sm:inline">{userEmail}</span>
          <button
            onClick={handleLogoutClick}
            className="px-4 py-2 bg-red-500 rounded-xl hover:bg-red-600 transition"
          >
            Logout
          </button>
        </div>
      ) : (
        <button className="px-4 py-2 bg-red-500 rounded-xl hover:bg-red-600 transition">
          Emergency SOS
        </button>
      )}
    </nav>
  )
}