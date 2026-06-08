import Navbar from "./components/Navbar";
import HeroSection from "./components/HeroSection";
import StatusCard from "./components/StatusCard";
import DangerAlert from "./components/DangerAlert";
import AudioVisualizer from "./components/AudioVisualizer.jsx";
import Footer from "./components/Footer";

export default function Home() {
  return (
    <main className="bg-gray-100 min-h-screen">
      <Navbar />

      <HeroSection />

      <div className="max-w-6xl mx-auto px-6 py-10 grid md:grid-cols-2 gap-6">
        <StatusCard />
        <DangerAlert />
      </div>

      <AudioVisualizer />

      <Footer />
    </main>
  );
}
