"use client"

import { useMicrophoneContext } from "@/app/lib/MicrophoneProvider"

export default function MicrophoneMonitor() {
  const { isRecording, recordingTime, permissionState, rmsLevel, lastPrediction, startRecording, stopRecording, error } = useMicrophoneContext()

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <div className="bg-white rounded-3xl shadow-lg p-8">
        <h1 className="text-3xl font-bold mb-6 text-center">Microphone Monitor</h1>

        <div className="mb-6">
          <div className="flex items-center justify-center gap-2 mb-4">
            <span className="text-sm font-medium text-gray-600">Status:</span>
            <span className={`px-3 py-1 rounded-full text-sm font-semibold ${
              isRecording
                ? "bg-green-100 text-green-800"
                : "bg-gray-100 text-gray-800"
            }`}>
              {isRecording ? "Active" : "Inactive"}
            </span>
          </div>

          <div className="h-48 bg-gradient-to-r from-gray-100 to-gray-200 rounded-2xl flex items-center justify-center mb-6">
            <div className="flex items-end gap-1 h-32">
              {Array.from({ length: 20 }).map((_, i) => (
                <div
                  key={i}
                  className="w-2 bg-blue-500 rounded-full"
                  style={{
                    height: "20%",
                    animation: isRecording ? "pulse-height 1s ease-in-out infinite" : "none",
                    animationDelay: `${i * 50}ms`,
                  }}
                />
              ))}
            </div>
          </div>

          {isRecording && (
            <div className="text-center mb-4">
              <span className="text-2xl font-mono font-bold text-gray-800">
                {formatTime(recordingTime)}
              </span>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="bg-gray-50 rounded-xl p-4">
              <p className="text-sm text-gray-500">RMS Level</p>
              <p className="text-xl font-bold">{rmsLevel.toFixed(4)}</p>
            </div>

            <div className="bg-gray-50 rounded-xl p-4">
              <p className="text-sm text-gray-500">Last Prediction</p>
              <p className="text-xl font-bold">
                {lastPrediction ? `${lastPrediction.prediction} (${Math.round(lastPrediction.confidence * 100)}%)` : 'None'}
              </p>
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
              <p className="text-sm text-red-600 text-center">{error}</p>
            </div>
          )}

          <div className="flex gap-4 justify-center">
            <button
              onClick={startRecording}
              disabled={isRecording}
              className={`px-6 py-3 rounded-xl font-medium transition-all ${
                isRecording
                  ? "bg-gray-300 cursor-not-allowed"
                  : "bg-blue-600 text-white hover:bg-blue-700 active:scale-95"
              }`}
            >
              Start Monitoring
            </button>
            <button
              onClick={stopRecording}
              disabled={!isRecording}
              className={`px-6 py-3 rounded-xl font-medium transition-all ${
                !isRecording
                  ? "bg-gray-300 cursor-not-allowed"
                  : "bg-red-600 text-white hover:bg-red-700 active:scale-95"
              }`}
            >
              Stop Monitoring
            </button>
          </div>

          <div className="mt-4 text-center">
            <span className="text-xs text-gray-500">
              Permission: {permissionState}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
