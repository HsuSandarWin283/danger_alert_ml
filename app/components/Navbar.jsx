'use client'

export default function Navbar({ userEmail, onLogout }) {
  return (
    <nav className="bg-black text-white px-8 py-4 flex justify-between items-center">
      <h1 className="text-2xl font-bold">AI Safety Companion</h1>

      {userEmail ? (
        <div className="flex items-center gap-4">
          <span className="text-sm">{userEmail}</span>
          <button
            onClick={onLogout}
            className="bg-red-500 px-5 py-2 rounded-xl hover:bg-red-600 transition"
          >
            Logout
          </button>
        </div>
      ) : (
        <button className="bg-red-500 bg-red-500/80 px-5 py-2 rounded-xl hover:bg-red-600 transition">
          Emergency SOS
        </button>
      )}
    </nav>
  );
}
