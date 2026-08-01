'use client'

import { useLang } from '@/app/lib/LanguageProvider'

export default function Footer() {
  const { t } = useLang()

  return (
    <footer className="bg-black text-white text-center py-6 mt-10">
      <p>
        {t('copyright')}
      </p>
    </footer>
  );
}
