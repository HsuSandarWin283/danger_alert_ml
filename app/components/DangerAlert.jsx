'use client'

import { useEffect, useState } from 'react'
import BackgroundMonitor from '@/app/lib/background-monitor'
import { useLang } from '@/app/lib/LanguageProvider'

function getDetectedAnswer(detail) {
  if (typeof detail === 'string') return detail

  if (!detail || typeof detail !== 'object') return null

  return (
    detail.detectedAnswer ||
    detail.answer ||
    detail.label ||
    detail.class ||
    detail.prediction ||
    detail.detected ||
    null
  )
}

function getConfidence(detail) {
  if (!detail || typeof detail !== 'object') return undefined

  return detail.confidence ?? detail.score ?? detail.probability
}

function formatConfidence(value) {
  if (value === undefined || value === null || value === '') return '—'

  const number = Number(value)

  if (Number.isNaN(number)) return String(value)

  return `${Math.round(number > 1 ? number : number * 100)}%`
}

export default function DangerAlert({ detectedAnswer, confidence }) {
  const [eventDetection, setEventDetection] = useState({})
  const [sending, setSending] = useState(false)
  const [lastSend, setLastSend] = useState(null)
  const [sendStatus, setSendStatus] = useState(null)
  const { t } = useLang()

  useEffect(() => {
    const handleDangerDetected = (event) => {
      const detail = event.detail || {}
      const nextAnswer = getDetectedAnswer(detail)
      const nextConfidence = getConfidence(detail)

      if (nextAnswer || nextConfidence !== undefined) {
        setEventDetection({
          detectedAnswer: nextAnswer,
          confidence: nextConfidence,
        })
      }
    }

    window.addEventListener('danger-detected', handleDangerDetected)

    return () => {
      window.removeEventListener('danger-detected', handleDangerDetected)
    }
  }, [])

  const displayAnswer =
    detectedAnswer || eventDetection.detectedAnswer || t('waitingForDetection')
  const displayConfidence = formatConfidence(
    confidence ?? eventDetection.confidence,
  )

  const handleEmergencyAlert = async () => {
    setSending(true)
    setLastSend(null)
    setSendStatus('sending')
    try {
      const result = await BackgroundMonitor.sendEmergencyAlert({
        dangerType: 'trouble',
        confidence: 1,
        alertMsg: 'needs help',
      })
      setLastSend({ ...result, success: true })
      setSendStatus('success')
    } catch (err) {
      setLastSend({ error: err.message ?? t('sendFailed'), success: false })
      setSendStatus('error')
    } finally {
      setSending(false)
    }
  }

  return (
    <div>
      <button
        onClick={handleEmergencyAlert}
        disabled={sending}
        className="w-full bg-black py-3 rounded-xl hover:bg-gray-900 transition disabled:opacity-50 mb-4 text-white"
      >
        {sending ? t('sending') : t('sendEmergencyAlert')}
      </button>
      {sendStatus && sendStatus !== 'idle' && (
        <div className={`text-sm p-3 rounded-xl border-2 ${
          sendStatus === 'success' ? 'bg-green-500 text-white border-green-400' :
          sendStatus === 'error' ? 'bg-red-500 text-white border-red-400' :
          'bg-yellow-500 text-white border-yellow-400'
        }`}>
          {sendStatus === 'success' ? `✓ ${t('sendSuccess')}` :
           sendStatus === 'error' ? `✗ Error: ${lastSend?.error ?? t('sendFailed')}` :
           t('sending')}
        </div>
      )}

      <div className="bg-red-500 text-white rounded-3xl shadow-lg p-8">
        <h2 className="text-3xl font-bold mb-6">
          {t('dangerDetection')}
        </h2>

        <div className="space-y-4">
          <div className="bg-white/20 p-4 rounded-xl">
            <p className="text-lg">{t('detectedSound')}</p>
            <h3 className="text-2xl font-bold">{displayAnswer}</h3>
          </div>

          <div className="bg-white/20 p-4 rounded-xl">
            <p className="text-lg">{t('confidence')}</p>
            <h3 className="text-2xl font-bold">{displayConfidence}</h3>
          </div>
        </div>
      </div>
    </div>
  )
}
