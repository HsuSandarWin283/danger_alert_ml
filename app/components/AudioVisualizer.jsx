"use client"

import { useMicrophoneContext } from "@/app/lib/MicrophoneProvider"
import { useEffect, useRef } from "react"

export default function AudioVisualizer() {
  const { isRecording, rmsLevel, lastPrediction } = useMicrophoneContext()
  const canvasRef = useRef(null)
  const audioContextRef = useRef(null)
  const analyserRef = useRef(null)
  const streamRef = useRef(null)

  useEffect(() => {
    let animationId
    let cancelled = false

    const stopStream = () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop())
        streamRef.current = null
      }
    }

    const closeAudioContext = () => {
      const audioContext = audioContextRef.current
      if (audioContext && audioContext.state !== 'closed') {
        void audioContext.close().catch(() => undefined)
      }
      audioContextRef.current = null
    }

    const drawSpectrogram = () => {
      if (cancelled || !canvasRef.current || !analyserRef.current) return
      const canvas = canvasRef.current
      const ctx = canvas.getContext('2d')
      const width = canvas.width
      const height = canvas.height

      const bufferLength = analyserRef.current.frequencyBinCount
      const dataArray = new Uint8Array(bufferLength)
      analyserRef.current.getByteFrequencyData(dataArray)

      ctx.fillStyle = 'rgb(0, 0, 0)'
      ctx.fillRect(0, 0, width, height)

      const barWidth = (width / bufferLength) * 2.5
      let x = 0

      for (let i = 0; i < bufferLength; i += 1) {
        const barHeight = dataArray[i] / 255 * height
        const hue = i / bufferLength * 120
        ctx.fillStyle = `hsl(${hue}, 100%, 50%)`
        ctx.fillRect(x, height - barHeight, barWidth, barHeight)
        x += barWidth + 1
      }

      animationId = requestAnimationFrame(drawSpectrogram)
    }

    if (isRecording) {
      navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
          if (cancelled) {
            stream.getTracks().forEach(track => track.stop())
            return
          }

          streamRef.current = stream
          audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)()
          const source = audioContextRef.current.createMediaStreamSource(stream)
          analyserRef.current = audioContextRef.current.createAnalyser()
          analyserRef.current.fftSize = 256
          source.connect(analyserRef.current)
          drawSpectrogram()
        })
        .catch(() => undefined)
    } else {
      if (animationId) cancelAnimationFrame(animationId)
      closeAudioContext()
      stopStream()
    }

    return () => {
      cancelled = true
      if (animationId) cancelAnimationFrame(animationId)
      closeAudioContext()
      stopStream()
    }
  }, [isRecording])

  return (
    <section className="max-w-6xl mx-auto px-6 py-10">
      <div className="bg-white rounded-3xl shadow-lg p-8">
        <h2 className="text-3xl font-bold mb-6">
          Live Audio Spectrogram
        </h2>

        <canvas
          ref={canvasRef}
          width={600}
          height={256}
          className="w-full h-64 bg-black rounded-2xl"
        />

        <div className="mt-4 grid md:grid-cols-2 gap-4">
          <div className="bg-gray-50 rounded-xl p-4">
            <p className="text-sm text-gray-500">RMS Level</p>
            <p className="text-xl font-bold">{rmsLevel.toFixed(4)}</p>
          </div>

          <div className="bg-gray-50 rounded-xl p-4">
            <p className="text-sm text-gray-500">Last Prediction</p>
            <p className="text-xl font-bold">
              {lastPrediction
                ? `${lastPrediction.prediction} (${Math.round(lastPrediction.confidence * 100)}%)`
                : 'Waiting for detection...'}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
