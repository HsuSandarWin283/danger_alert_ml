'use client'

import { useLang } from '@/app/lib/LanguageProvider'
import { Capacitor } from '@capacitor/core'

export default function LanguageSwitch() {
  const { lang, setLang } = useLang()

  const handleSetLang = (l: 'en' | 'my') => {
    setLang(l)
    if (Capacitor.isNativePlatform()) {
      import('@/app/lib/background-monitor').then(({ default: BackgroundMonitor }) => {
        BackgroundMonitor.setLanguage({ lang: l })
      })
    }
  }

  return (
    <div className="flex items-center bg-gray-800 rounded-full p-0.5">
      <button
        onClick={() => handleSetLang('en')}
        className={`px-3 py-1 text-xs font-semibold rounded-full transition ${
          lang === 'en'
            ? 'bg-white text-black'
            : 'text-gray-400 hover:text-white'
        }`}
      >
        EN
      </button>
      <button
        onClick={() => handleSetLang('my')}
        className={`px-3 py-1 text-xs font-semibold rounded-full transition ${
          lang === 'my'
            ? 'bg-white text-black'
            : 'text-gray-400 hover:text-white'
        }`}
      >
        မြန်မာ
      </button>
    </div>
  )
}
