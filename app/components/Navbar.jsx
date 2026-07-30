'use client'

import { useRouter } from 'next/navigation'

function BackIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
      <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" />
    </svg>
  )
}

function HelpHistoryIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
      <path d="M12 22a2.5 2.5 0 0 0 2.5-2.5h-5A2.5 2.5 0 0 0 12 22zm7.5-6.5V11a8 8 0 1 0-15 0v4.5l-1.5 1.5v2h17v-2l-1.6-1.5z" />
    </svg>
  )
}

function ProfileIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
      <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm0 2c-4.42 0-8 1.79-8 4v2h16v-2c0-2.21-3.58-4-8-4z" />
    </svg>
  )
}

function LogoutIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
      <path d="M10.09 15.59 11.5 17l5-5-5-5-1.41 1.41L12.67 11H3v2h9.67l-2.58 2.59zM19 3H5a2 2 0 0 0-2 2v4h2V5h14v14H5v-4H3v4a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2z" />
    </svg>
  )
}

export default function Navbar({ userEmail, onLogout, showBack, onBack }) {
  const router = useRouter()
  const handleLogoutClick = () => {
    if (window.confirm('Are you sure you want to logout?')) {
      onLogout?.()
    }
  }

  return (
    <nav className="bg-black text-white px-6 py-4 flex justify-between items-center">
      <div className="flex items-center gap-3">
        {showBack ? (
          <button
            onClick={onBack || (() => router.push('/'))}
            className="p-2 bg-gray-800 rounded-full hover:bg-gray-700 transition"
            title="Back"
          >
            <BackIcon />
          </button>
        ) : (
          <h1 className="text-2xl font-bold">AI Safety Companion</h1>
        )}
      </div>

      {userEmail && !showBack ? (
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push('/help-history')}
            className="p-2 bg-gray-800 rounded-full hover:bg-gray-700 transition"
            title="Help History"
          >
            <HelpHistoryIcon />
          </button>
          <button
            onClick={() => router.push('/profile')}
            className="p-2 bg-gray-800 rounded-full hover:bg-gray-700 transition"
            title="Profile"
          >
            <ProfileIcon />
          </button>
          <span className="text-sm hidden sm:inline">{userEmail}</span>
          <button
            onClick={handleLogoutClick}
            className="p-2 bg-red-500 rounded-full hover:bg-red-600 transition"
            title="Logout"
          >
            <LogoutIcon />
          </button>
        </div>
      ) : !userEmail ? (
        <button className="px-4 py-2 bg-red-500 rounded-xl hover:bg-red-600 transition">
          Emergency SOS
        </button>
      ) : null}
    </nav>
  )
}
