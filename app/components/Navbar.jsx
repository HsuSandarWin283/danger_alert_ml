export default function Navbar() {
  return (
    <nav className="bg-black text-white px-8 py-4 flex justify-between items-center">
      <h1 className="text-2xl font-bold">
        AI Safety Companion
      </h1>

      <button className="bg-red-500 px-5 py-2 rounded-xl hover:bg-red-600 transition">
        Emergency SOS
      </button>
      
    </nav>
  );
}
