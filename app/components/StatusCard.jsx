"use client"

import { useMicrophoneContext } from "@/app/lib/MicrophoneProvider"

export default function StatusCard() {
  const { isRecording } = useMicrophoneContext()

  return (
    <div className="bg-white rounded-3xl shadow-lg p-8">
      <h2 className="text-3xl font-bold mb-6">
        System Status
      </h2>

      <div className="space-y-4">
        <div className="flex justify-between">
          <span>Microphone</span>
          <span className={`font-bold ${
            isRecording ? "text-green-600" : "text-red-600"
          }`}>
            {isRecording ? "Active" : "Inactive"}
          </span>
        </div>

        <div className="flex justify-between">
          <span>AI Model</span>
          <span className="text-green-600 font-bold">Running</span>
        </div>

        <div className="flex justify-between">
          <span>Environment</span>
          <span className="text-yellow-500 font-bold">Monitoring</span>
        </div>
      </div>
    </div>
  );
}