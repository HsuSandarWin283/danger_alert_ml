"use client"

import { createContext, useContext, useState, useRef, useCallback, ReactNode } from "react"

interface MicrophoneContextValue {
  isRecording: boolean
  recordingTime: number
  permissionState: "granted" | "denied" | "prompt" | "unknown"
  error: string | null
  startRecording: () => Promise<void>
  stopRecording: () => void
}

const MicrophoneContext = createContext<MicrophoneContextValue | null>(null)

export function MicrophoneProvider({ children }: { children: ReactNode }) {
  const [isRecording, setIsRecording] = useState(false)
  const [recordingTime, setRecordingTime] = useState(0)
  const [permissionState, setPermissionState] = useState<"granted" | "denied" | "prompt" | "unknown">("unknown")
  const [error, setError] = useState<string | null>(null)
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const timerRef = useRef<NodeJS.Timeout | null>(null)

  const startRecording = useCallback(async () => {
    setError(null)
    
    if (!window?.navigator?.mediaDevices?.getUserMedia) {
      setError("Microphone API not available. Requires secure context (HTTPS).")
      setPermissionState("denied")
      return
    }
    
    try {
      const stream = await window.navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      setPermissionState("granted")
      
      if (!window.MediaRecorder) {
        setError("MediaRecorder API not supported in this browser")
        setPermissionState("denied")
        return
      }
      
      const mediaRecorder = new MediaRecorder(stream)
      mediaRecorderRef.current = mediaRecorder
      
      mediaRecorder.start()
      setIsRecording(true)
      setRecordingTime(0)
      
      timerRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1)
      }, 1000)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to access microphone"
      setError(errorMessage)
      setPermissionState("denied")
    }
  }, [])

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop()
    }
    
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
    
    setIsRecording(false)
    
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  return (
    <MicrophoneContext.Provider
      value={{
        isRecording,
        recordingTime,
        permissionState,
        error,
        startRecording,
        stopRecording,
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