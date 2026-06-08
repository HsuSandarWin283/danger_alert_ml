export default function DangerAlert() {
  return (
    <div className="bg-red-500 text-white rounded-3xl shadow-lg p-8">
      <h2 className="text-3xl font-bold mb-6">
        Danger Detection
      </h2>

      <div className="space-y-4">
        <div className="bg-white/20 p-4 rounded-xl">
          <p className="text-lg">Detected Sound</p>
          <h3 className="text-2xl font-bold">Gunshot</h3>
        </div>

        <div className="bg-white/20 p-4 rounded-xl">
          <p className="text-lg">Confidence</p>
          <h3 className="text-2xl font-bold">92%</h3>
        </div>

        <button className="w-full bg-black py-3 rounded-xl hover:bg-gray-900 transition">
          Send Emergency Alert
        </button>
      </div>
    </div>
  );
}