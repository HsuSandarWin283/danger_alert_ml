"use client"

import { useMicrophoneContext } from "@/app/lib/MicrophoneProvider"
import { useEffect, useState, useRef } from "react"

export default function AudioVisualizer() {
  const { isRecording, audioBlob, predictAudio } = useMicrophoneContext()
  const [prediction, setPrediction] = useState(null)
  const canvasRef = useRef(null)
  const audioContextRef = useRef(null)
  const analyserRef = useRef(null)

  useEffect(() => {
    if (!isRecording && audioBlob) {
      predictAudio().then(setPrediction)
    }
  }, [isRecording, audioBlob, predictAudio])

  useEffect(() => {
    let animationId
    const drawSpectrogram = () => {
      if (!canvasRef.current || !analyserRef.current) return
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
      let barHeight
      let x = 0
      
      for (let i = 0; i < bufferLength; i++) {
        barHeight = dataArray[i] / 255 * height
        const hue = i / bufferLength * 120
        ctx.fillStyle = `hsl(${hue}, 100%, 50%)`
        ctx.fillRect(x, height - barHeight, barWidth, barHeight)
        x += barWidth + 1
      }
      
      animationId = requestAnimationFrame(drawSpectrogram)
    }
    
    if (isRecording) {
      navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)()
        const source = audioContextRef.current.createMediaStreamSource(stream)
        analyserRef.current = audioContextRef.current.createAnalyser()
        analyserRef.current.fftSize = 256
        source.connect(analyserRef.current)
        drawSpectrogram()
      })
    } else {
      if (animationId) cancelAnimationFrame(animationId)
      if (audioContextRef.current) audioContextRef.current.close()
    }
    
    return () => {
      if (animationId) cancelAnimationFrame(animationId)
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

        {/* {prediction && (
          <div className="mt-4 p-4 bg-gray-100 rounded-xl">
            <p className="text-lg font-bold">Detected: {prediction.prediction}</p>
            <p className="text-sm">Confidence: {(prediction.confidence * 100).toFixed(1)}%</p>
          </div>
        )} */}
      </div>
    </section>
  );
}
