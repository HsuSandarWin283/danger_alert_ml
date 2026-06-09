'use client'

import { useRouter } from 'next/navigation'

export default function HeroSection() {
  const router = useRouter()

  return (
    <section className="text-center py-16 px-6 bg-gradient-to-r from-black to-gray-800 text-white">
      <h1 className="text-5xl font-bold mb-6">
        AI-Powered Personal Safety
      </h1>

      <p className="text-lg max-w-3xl mx-auto text-gray-300">
        Real-time danger sound detection using CNN,
        Mel-Spectrograms, and emergency alert systems.
      </p>

      <div className="mt-8 flex flex-col sm:flex-row gap-4 justify-center">
        <button className="bg-red-500 px-8 py-3 rounded-2xl text-lg hover:bg-red-600 transition">
          Start Listening
        </button>
        <button
          onClick={() => router.push('/trusted-group')}
          className="bg-blue-600 px-8 py-3 rounded-2xl text-lg hover:bg-blue-700 transition"
        >
          Trusted Group
        </button>
      </div>
    </section>
  )
}