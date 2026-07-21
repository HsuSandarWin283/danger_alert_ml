"use client"

import { useEffect, useRef, useState } from "react"
import { useMicrophoneContext } from "@/app/lib/MicrophoneProvider"

type StatusCardProps = {
  isMonitoring?: boolean
  error?: string | null
}

export default function StatusCard({ isMonitoring = false, error = null }: StatusCardProps) {
  const { isRecording } = useMicrophoneContext()
  const [apiStatus, setApiStatus] = useState("checking")
  const retryRef = useRef(0)
  const MAX_RETRIES = 10

  const apiBaseUrl =
    process.env.NEXT_PUBLIC_DANGER_API_URL || 'https://danger-alert-ml.onrender.com';

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    const checkHealth = async () => {
      try {
        const controller = new AbortController()
        const timeout = setTimeout(() => controller.abort(), 15000)
        const res = await fetch(`${apiBaseUrl}/health`, { signal: controller.signal })
        clearTimeout(timeout)
        const data = await res.json()
        if (!cancelled) {
          setApiStatus(data.status === "healthy" ? "healthy" : "unhealthy")
        }
      } catch (err) {
        console.error("API health check failed:", err)
        if (!cancelled && retryRef.current < MAX_RETRIES) {
          retryRef.current += 1
          const delay = Math.min(3000 * retryRef.current, 15000)
          timer = setTimeout(checkHealth, delay)
        } else if (!cancelled) {
          setApiStatus("unhealthy")
        }
      }
    }

    checkHealth()

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [apiBaseUrl])

  const microphoneActive = isMonitoring || isRecording

  return (
    <div className="bg-white rounded-3xl shadow-lg p-8">
      <h2 className="text-3xl font-bold mb-6">
        System Status
      </h2>

      <div className="space-y-4">
        <div className="flex justify-between">
          <span>Microphone</span>
          <span className={`font-bold ${
            microphoneActive ? "text-green-600" : "text-gray-500"
          }`}>
            {microphoneActive ? "Active" : "Inactive"}
          </span>
        </div>

        <div className="flex justify-between">
          <span>AI Model</span>
          <span className={`font-bold ${
            apiStatus === "healthy" ? "text-green-600" : apiStatus === "checking" ? "text-yellow-500" : "text-red-600"
          }`}>
            {apiStatus === "healthy" ? "Running" : apiStatus === "checking" ? "Checking..." : "Offline"}
          </span>
        </div>

        <div className="flex justify-between">
          <span>Environment</span>
          <span className="text-yellow-500 font-bold">Monitoring</span>
        </div>

        {error && (
          <div className="bg-red-50 text-red-700 rounded-xl p-3 text-sm">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
