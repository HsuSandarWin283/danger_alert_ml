'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

type PredictionResponse = {
  prediction: string
  confidence: number
  probabilities?: Record<string, number>
  rms?: number
}

export type DangerAlertPayload = {
  detectedAnswer: string
  confidence: number
  probabilities?: Record<string, number>
  rms: number
}

type PredictionApiResponse = {
  prediction?: string
  detectedAnswer?: string
  answer?: string
  confidence?: number
  score?: number
  probability?: number
  probabilities?: Record<string, number>
  [key: string]: unknown
}

type UseDangerSoundMonitorReturn = {
  isMonitoring: boolean
  isRecording: boolean
  rmsLevel: number
  lastPrediction: PredictionResponse | null
  error: string | null
  startMonitoring: () => Promise<void>
  stopMonitoring: () => void
}

const DEFAULT_PREDICT_URL = 'http://localhost:8000/predict'
const CHUNK_MS = 2000
const RMS_CHECK_MS = 200
const RMS_THRESHOLD = 0.015
const CONFIDENCE_THRESHOLD = 0.8
const DUPLICATE_ALERT_MS = 10000
const DANGER_LABELS = new Set(['gunshot', 'scream', 'glass_break'])

function getPredictUrl() {
  return process.env.NEXT_PUBLIC_DANGER_PREDICT_URL || DEFAULT_PREDICT_URL
}

function calculateRms(samples: Float32Array | number[]) {
  let sum = 0

  for (let i = 0; i < samples.length; i += 1) {
    const sample = Number(samples[i])
    sum += sample * sample
  }

  return Math.sqrt(sum / samples.length)
}

async function calculateBlobRms(blob: Blob, audioContext: AudioContext) {
  const arrayBuffer = await blob.arrayBuffer()
  const audioBuffer = await audioContext.decodeAudioData(arrayBuffer)
  const channel = audioBuffer.getChannelData(0)
  return calculateRms(channel)
}

function getSupportedMimeType() {
  const mimeTypes = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
  ]

  if (!window.MediaRecorder || !window.MediaRecorder.isTypeSupported) {
    return ''
  }

  return mimeTypes.find((mimeType) => window.MediaRecorder.isTypeSupported(mimeType)) || ''
}

function normalizeLabel(value: string) {
  return value.toLowerCase().trim().replace(/[\s-]+/g, '_')
}

function formatLabel(value: string) {
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function normalizePrediction(data: PredictionApiResponse): PredictionResponse {
  const prediction = normalizeLabel(
    String(data?.prediction ?? data?.detectedAnswer ?? data?.answer ?? ''),
  )
  const confidence = Number(data?.confidence ?? data?.score ?? data?.probability ?? 0)

  return {
    prediction,
    confidence,
    probabilities: data?.probabilities || {},
  }
}

export function useDangerSoundMonitor(
  onDangerDetected?: (payload: DangerAlertPayload) => void,
): UseDangerSoundMonitorReturn {
  const [isMonitoring, setIsMonitoring] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [rmsLevel, setRmsLevel] = useState(0)
  const [lastPrediction, setLastPrediction] = useState<PredictionResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const intervalRef = useRef<number | null>(null)
  const currentRmsRef = useRef(0)
  const isPredictingRef = useRef(false)
  const lastAlertRef = useRef<{ label: string; timestamp: number } | null>(null)
  const mountedRef = useRef(false)

  const stopMonitoring = useCallback(() => {
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current)
      intervalRef.current = null
    }

    const recorder = mediaRecorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop()
    }
    mediaRecorderRef.current = null

    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null

    audioContextRef.current?.close().catch(() => undefined)
    audioContextRef.current = null

    isPredictingRef.current = false
    setIsRecording(false)
    setIsMonitoring(false)
  }, [])

  useEffect(() => {
    mountedRef.current = true

    return () => {
      mountedRef.current = false
      stopMonitoring()
    }
  }, [stopMonitoring])

  const startMonitoring = useCallback(async () => {
    setError(null)

    if (!window.navigator?.mediaDevices?.getUserMedia) {
      setError('Microphone API is not available in this browser.')
      return
    }

    if (!window.MediaRecorder) {
      setError('MediaRecorder API is not supported in this browser.')
      return
    }

    try {
      const stream = await window.navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })

      streamRef.current = stream

      const AudioContextConstructor =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext

      if (!AudioContextConstructor) {
        throw new Error('AudioContext API is not available in this browser.')
      }

      const audioContext = new AudioContextConstructor()
      audioContextRef.current = audioContext

      const analyser = audioContext.createAnalyser()
      analyser.fftSize = 1024
      const analyserData = new Float32Array(analyser.fftSize)
      const source = audioContext.createMediaStreamSource(stream)
      source.connect(analyser)

      intervalRef.current = window.setInterval(() => {
        analyser.getFloatTimeDomainData(analyserData)
        const rms = calculateRms(analyserData)
        currentRmsRef.current = rms
        setRmsLevel(rms)
      }, RMS_CHECK_MS)

      const mimeType = getSupportedMimeType()
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream)

      mediaRecorderRef.current = recorder

      recorder.ondataavailable = async (event) => {
        if (!event.data || event.data.size === 0 || isPredictingRef.current) {
          return
        }

        const blob = event.data
        const rms = await calculateBlobRms(blob, audioContext).catch(() => currentRmsRef.current)

        currentRmsRef.current = rms
        setRmsLevel(rms)

        if (rms < RMS_THRESHOLD) {
          return
        }

        isPredictingRef.current = true

        try {
          const formData = new FormData()
          formData.append('file', blob, `monitoring-${Date.now()}.webm`)

          const response = await fetch(getPredictUrl(), {
            method: 'POST',
            body: formData,
          })

          if (!response.ok) {
            throw new Error(`Prediction failed with status ${response.status}`)
          }

          const data = await response.json()
          const prediction = normalizePrediction(data)
          prediction.rms = rms
          setLastPrediction(prediction)

          if (
            DANGER_LABELS.has(prediction.prediction) &&
            prediction.confidence >= CONFIDENCE_THRESHOLD
          ) {
            const now = Date.now()
            const lastAlert = lastAlertRef.current
            const isDuplicate =
              lastAlert &&
              lastAlert.label === prediction.prediction &&
              now - lastAlert.timestamp < DUPLICATE_ALERT_MS

            if (!isDuplicate) {
              lastAlertRef.current = {
                label: prediction.prediction,
                timestamp: now,
              }

              const payload: DangerAlertPayload = {
                detectedAnswer: formatLabel(prediction.prediction),
                confidence: prediction.confidence,
                probabilities: prediction.probabilities,
                rms,
              }

              window.dispatchEvent(
                new CustomEvent('danger-detected', {
                  detail: payload,
                }),
              )

              if (mountedRef.current) {
                onDangerDetected?.(payload)
              }
            }
          }
        } catch (err) {
          const message = err instanceof Error ? err.message : 'Prediction failed'
          setError(message)
        } finally {
          isPredictingRef.current = false
        }
      }

      recorder.start(CHUNK_MS)
      setIsRecording(true)
      setIsMonitoring(true)
    } catch (err) {
      stopMonitoring()
      const message = err instanceof Error ? err.message : 'Failed to start microphone monitoring'
      setError(message)
    }
  }, [onDangerDetected, stopMonitoring])

  return {
    isMonitoring,
    isRecording,
    rmsLevel,
    lastPrediction,
    error,
    startMonitoring,
    stopMonitoring,
  }
}
