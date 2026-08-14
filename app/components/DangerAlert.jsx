'use client'

import { useEffect, useState } from 'react'
import BackgroundMonitor from '@/app/lib/background-monitor'
import { useLang } from '@/app/lib/LanguageProvider'
import { useAuth } from '@/app/auth-provider'
import { saveHelpMessage } from '@/app/lib/help-history'
import { getUserProfile } from '@/app/lib/user-profile'

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

function getLocation() {
  return new Promise((resolve) => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      resolve({ lat: undefined, lng: undefined, locationName: '' })
      return
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
          locationName: '',
        })
      },
      () => {
        resolve({ lat: undefined, lng: undefined, locationName: '' })
      },
      { enableHighAccuracy: false, timeout: 5000, maximumAge: 300000 }
    )
  })
}

export default function DangerAlert({ detectedAnswer, confidence }) {
  const [eventDetection, setEventDetection] = useState({})
  const [sending, setSending] = useState(false)
  const [lastSend, setLastSend] = useState(null)
  const [sendStatus, setSendStatus] = useState(null)
  const [showOverlay, setShowOverlay] = useState(false)
  const { t } = useLang()
  const { user } = useAuth()

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
        setShowOverlay(true)
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

  const sendDangerHelp = async () => {
    if (!user) return

    setSending(true)
    setLastSend(null)
    setSendStatus('sending')

    try {
      let displayName = user.displayName || 'User'
      try {
        const profile = await getUserProfile(user.uid)
        if (profile?.name) displayName = profile.name
      } catch (e) {
        console.warn('[DangerAlert] Failed to load user profile', e)
      }

      const loc = await getLocation()
      const isNative =
        typeof window !== 'undefined' &&
        window.Capacitor &&
        window.Capacitor.isNativePlatform &&
        window.Capacitor.isNativePlatform()

      if (isNative) {
        const result = await BackgroundMonitor.sendEmergencyAlert({
          dangerType: displayAnswer,
          confidence: 1,
          alertMsg: `${displayName} ${t('needsHelp')}`,
        })
        setLastSend({ ...result, success: true })
        setSendStatus('success')
      } else {
        const auth = (await import('firebase/auth')).getAuth()
        const { getFirestore, collection, query, where, getDocs } = await import('firebase/firestore')
        const db = getFirestore()
        const currentUser = auth.currentUser

        if (!currentUser) {
          throw new Error('Not authenticated')
        }

        const q = query(collection(db, 'group_members'), where('groupId', '==', currentUser.uid))
        const snapshot = await getDocs(q)
        const receiverIds = []
        snapshot.docs.forEach((d) => {
          const data = d.data()
          if (data.userId) receiverIds.push(data.userId)
        })

        if (receiverIds.length === 0) {
          setLastSend({ sent: 0, total: 0, success: true })
          setSendStatus('success')
          return
        }

        await saveHelpMessage({
          senderId: currentUser.uid,
          senderName: displayName,
          receiverIds,
          dangerType: displayAnswer,
          alertMsg: `${displayName} ${t('needsHelp')}`,
          lat: loc.lat,
          lng: loc.lng,
          locationName: loc.locationName,
        })

        setLastSend({ sent: receiverIds.length, total: receiverIds.length, success: true })
        setSendStatus('success')
      }
    } catch (err) {
      setLastSend({ error: err.message ?? t('sendFailed'), success: false })
      setSendStatus('error')
    } finally {
      setSending(false)
    }
  }

  const sendEmergencyAlert = async () => {
    if (!user) return

    setSending(true)
    setLastSend(null)
    setSendStatus('sending')

    try {
      let displayName = user.displayName || 'User'
      try {
        const profile = await getUserProfile(user.uid)
        if (profile?.name) displayName = profile.name
      } catch (e) {
        console.warn('[DangerAlert] Failed to load user profile', e)
      }

      const isNative =
        typeof window !== 'undefined' &&
        window.Capacitor &&
        window.Capacitor.isNativePlatform &&
        window.Capacitor.isNativePlatform()

      if (isNative) {
        const result = await BackgroundMonitor.sendEmergencyAlert({
          dangerType: 'TROUBLE',
          confidence: 1,
          alertMsg: `${displayName} ${t('needsHelp')}`,
        })
        setLastSend({ ...result, success: true })
        setSendStatus('success')
      } else {
        const auth = (await import('firebase/auth')).getAuth()
        const { getFirestore, collection, query, where, getDocs } = await import('firebase/firestore')
        const db = getFirestore()
        const currentUser = auth.currentUser

        if (!currentUser) {
          throw new Error('Not authenticated')
        }

        const q = query(collection(db, 'group_members'), where('groupId', '==', currentUser.uid))
        const snapshot = await getDocs(q)
        const receiverIds = []
        snapshot.docs.forEach((d) => {
          const data = d.data()
          if (data.userId) receiverIds.push(data.userId)
        })

        if (receiverIds.length === 0) {
          setLastSend({ sent: 0, total: 0, success: true })
          setSendStatus('success')
          return
        }

        await saveHelpMessage({
          senderId: currentUser.uid,
          senderName: displayName,
          receiverIds,
          dangerType: 'TROUBLE',
          alertMsg: `${displayName} ${t('needsHelp')}`,
        })

        setLastSend({ sent: receiverIds.length, total: receiverIds.length, success: true })
        setSendStatus('success')
      }
    } catch (err) {
      setLastSend({ error: err.message ?? t('sendFailed'), success: false })
      setSendStatus('error')
    } finally {
      setSending(false)
    }
  }

  const handleImOk = () => {
    setShowOverlay(false)
  }

  const handleSendHelp = async () => {
    await sendDangerHelp()
    setShowOverlay(false)
  }

  return (
    <div>
      <button
        onClick={sendEmergencyAlert}
        disabled={sending}
        className="w-full bg-black py-6 rounded-xl hover:bg-gray-900 transition disabled:opacity-50 mb-4 text-white"
      >
        {sending ? t('sending') : t('sendEmergencyAlert')}
      </button>
      {sendStatus && sendStatus !== 'idle' && (
        <div className={`text-sm p-3 rounded-xl border-2 ${
          sendStatus === 'success' ? 'bg-green-500 text-white text-center border-green-400' :
          sendStatus === 'error' ? 'bg-red-500 text-white text-center border-red-400' :
          'bg-yellow-500 text-white border-yellow-400'
        }`}>
          {sendStatus === 'success' ? `✓ ${lastSend?.sent ? t('helpSentSuccess') : t('sendSuccess')}` :
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

      {showOverlay && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/80 p-4 pt-10">
          <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-md w-full">
            <div className="text-center mb-8">
              <div className="text-6xl mb-4">⚠️</div>
              <h2 className="text-3xl font-bold text-gray-900 mb-2">
                Danger : {displayAnswer}
              </h2>
              <p className="text-xl font-semibold text-gray-800 mb-6">
                {t('dangerSoundFoundNear')}
              </p>
              <p className="text-xl font-semibold text-gray-800">
                {t('areYouOk')}
              </p>
            </div>

            <div className="space-y-3">
              <button
                onClick={handleImOk}
                className="w-full bg-green-500 text-white py-4 rounded-xl text-lg font-semibold hover:bg-green-600 transition active:scale-95"
              >
                {t('imOk')}
              </button>
              <button
                onClick={handleSendHelp}
                disabled={sending}
                className="w-full bg-red-500 text-white py-4 rounded-xl text-lg font-semibold hover:bg-red-600 transition active:scale-95 disabled:opacity-50"
              >
                {sending ? t('sending') : t('imNotOkSendHelp')}
              </button>
            </div>

            {sendStatus && sendStatus !== 'idle' && (
              <div className={`mt-4 text-sm p-3 rounded-xl border-2 ${
                sendStatus === 'success' ? 'bg-green-500 text-white border-green-400' :
                sendStatus === 'error' ? 'bg-red-500 text-white border-red-400' :
                'bg-yellow-500 text-white border-yellow-400'
              }`}>
                {sendStatus === 'success' ? `✓ ${lastSend?.sent ? t('helpSentSuccess') : t('sendSuccess')}` :
                 sendStatus === 'error' ? `✗ ${lastSend?.error ?? t('helpSentFailed')}` :
                 t('sending')}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
