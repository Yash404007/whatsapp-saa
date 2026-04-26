import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-white mb-4">
          🚀 WhatsApp SaaS Platform
        </h1>
        <p className="text-gray-400 mb-8">
          Multi-tenant WhatsApp AI Bot Platform
        </p>
        <Link
          href="/dashboard"
          className="bg-green-600 hover:bg-green-700 text-white px-8 py-3 rounded-lg font-semibold transition"
        >
          Go to Dashboard
        </Link>
      </div>
    </main>
  );
}