"use client"

import { createContext, useContext } from "react"
import { useDangerSoundMonitor } from "@/app/lib/useDangerSoundMonitor"

type PredictionResult = {
  prediction: string
  confidence: number
  probabilities: Record<string, number>
}

interface MicrophoneContextValue {
  isRecording: boolean
  recordingTime: number
  permissionState: "granted" | "denied" | "prompt" | "unknown"
  error: string | null
  audioBlob: Blob | null
  rmsLevel: number
  lastPrediction: PredictionResult | null
  startRecording: () => Promise<void>
  stopRecording: () => void
  predictAudio: () => Promise<PredictionResult | null>
}

const MicrophoneContext = createContext<MicrophoneContextValue | null>(null)

export function MicrophoneProvider({ children }: { children: React.ReactNode }) {
  const {
    isMonitoring,
    isRecording,
    rmsLevel,
    lastPrediction,
    error,
    startMonitoring,
    stopMonitoring,
  } = useDangerSoundMonitor()

  const predictAudio = async () => {
    if (!lastPrediction) return null

    return {
      prediction: lastPrediction.prediction,
      confidence: lastPrediction.confidence,
      probabilities: lastPrediction.probabilities || {},
    }
  }

  return (
    <MicrophoneContext.Provider
      value={{
        isRecording: isMonitoring || isRecording,
        recordingTime: 0,
        permissionState: isRecording ? "granted" : "unknown",
        error,
        audioBlob: null,
        rmsLevel,
        lastPrediction: lastPrediction
          ? {
              prediction: lastPrediction.prediction,
              confidence: lastPrediction.confidence,
              probabilities: lastPrediction.probabilities || {},
            }
          : null,
        startRecording: startMonitoring,
        stopRecording: stopMonitoring,
        predictAudio,
      }}
    >
      {children}
    </MicrophoneContext.Provider>
  )
}

export function useMicrophoneContext() {
  const context = useContext(MicrophoneContext)
  if (!context) {
    throw new Error("useMicrophoneContext must be used within MicrophoneProvider")
  }
  return context
}
