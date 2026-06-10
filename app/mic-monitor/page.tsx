import MicrophoneMonitor from "@/app/components/MicrophoneMonitor"

export const metadata = {
  title: "Microphone Monitor | AI Safety Companion",
  description: "Monitor microphone for danger detection",
}

export default function MicrophonePage() {
  return (
    <main className="bg-gray-100 min-h-screen">
      <MicrophoneMonitor />
    </main>
  )
}