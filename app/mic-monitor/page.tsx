'use client'

import MicrophoneMonitor from "@/app/components/MicrophoneMonitor"
import { useLang } from "@/app/lib/LanguageProvider"

export default function MicrophonePage() {
  const { t } = useLang()

  return (
    <main className="bg-gray-100 min-h-screen">
      <MicrophoneMonitor />
    </main>
  )
}
