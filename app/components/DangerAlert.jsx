import { useEffect, useState } from 'react'

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
    detectedAnswer || eventDetection.detectedAnswer || 'Waiting for detection...'
  const displayConfidence = formatConfidence(
    confidence ?? eventDetection.confidence,
  )

  return (
    <div className="bg-red-500 text-white rounded-3xl shadow-lg p-8">
      <h2 className="text-3xl font-bold mb-6">
        Danger Detection
      </h2>

      <div className="space-y-4">
        <div className="bg-white/20 p-4 rounded-xl">
          <p className="text-lg">Detected Sound</p>
          <h3 className="text-2xl font-bold">{displayAnswer}</h3>
        </div>

        <div className="bg-white/20 p-4 rounded-xl">
          <p className="text-lg">Confidence</p>
          <h3 className="text-2xl font-bold">{displayConfidence}</h3>
        </div>

        <button className="w-full bg-black py-3 rounded-xl hover:bg-gray-900 transition">
          Send Emergency Alert
        </button>
      </div>
    </div>
  )
}
