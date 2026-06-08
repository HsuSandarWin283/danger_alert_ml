export default function StatusCard() {
  return (
    <div className="bg-white rounded-3xl shadow-lg p-8">
      <h2 className="text-3xl font-bold mb-6">
        System Status
      </h2>

      <div className="space-y-4">
        <div className="flex justify-between">
          <span>Microphone</span>
          <span className="text-green-600 font-bold">Active</span>
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