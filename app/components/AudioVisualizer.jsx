export default function AudioVisualizer() {
  return (
    <section className="max-w-6xl mx-auto px-6 py-10">
      <div className="bg-white rounded-3xl shadow-lg p-8">
        <h2 className="text-3xl font-bold mb-6">
          Live Audio Spectrogram
        </h2>

        <div className="h-64 bg-black rounded-2xl flex items-center justify-center text-green-400 text-xl font-bold">
          Spectrogram Visualization Here
        </div>
      </div>
    </section>
  );
}
