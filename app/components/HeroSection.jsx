export default function HeroSection() {
  return (
    <section className="text-center py-16 px-6 bg-gradient-to-r from-black to-gray-800 text-white">
      <h1 className="text-5xl font-bold mb-6">
        AI-Powered Personal Safety
      </h1>

      <p className="text-lg max-w-3xl mx-auto text-gray-300">
        Real-time danger sound detection using CNN,
        Mel-Spectrograms, and emergency alert systems.
      </p>

      <button className="mt-8 bg-red-500 px-8 py-3 rounded-2xl text-lg hover:bg-red-600 transition">
        Start Listening
      </button>
    </section>
  );
}
