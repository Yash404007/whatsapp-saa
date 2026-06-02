"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import axios from "axios";

interface Client {
  id: string;
  business_name: string;
  business_type: string;
  bot_name: string;
  is_active: boolean;
  created_at: string;
}

export default function Dashboard() {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  useEffect(() => {
    fetchClients();
  }, []);

  const fetchClients = () => {
    axios.get(`${process.env.NEXT_PUBLIC_API_URL}/admin/clients`)
      .then(res => { setClients(res.data); setLoading(false); })
      .catch(() => setLoading(false));
  };

  const deleteClient = async (id: string, name: string) => {
    if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;
    setDeletingId(id);
    try {
      await axios.delete(`${process.env.NEXT_PUBLIC_API_URL}/admin/clients/${id}`);
      setClients(prev => prev.filter(c => c.id !== id));
    } catch (err: any) {
      alert(`❌ Error: ${err.message}`);
    } finally {
      setDeletingId(null);
    }
  };

  const toggleStatus = async (id: string, current: boolean) => {
    setTogglingId(id);
    try {
      await axios.put(`${process.env.NEXT_PUBLIC_API_URL}/admin/clients/${id}`, {
        is_active: !current,
      });
      setClients(prev => prev.map(c => c.id === id ? { ...c, is_active: !current } : c));
    } catch (err: any) {
      alert(`❌ Error: ${err.message}`);
    } finally {
      setTogglingId(null);
    }
  };

  return (
    <main className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-6xl mx-auto">

        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold">🤖 Admin Dashboard</h1>
            <p className="text-gray-400 mt-1">Manage all your WhatsApp bots</p>
          </div>
          <Link
            href="/onboard"
            className="bg-green-600 hover:bg-green-700 text-white px-6 py-3 rounded-lg font-semibold transition"
          >
            + Add New Bot
          </Link>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <p className="text-gray-400 text-sm">Total Bots</p>
            <p className="text-3xl font-bold text-white mt-1">{clients.length}</p>
          </div>
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <p className="text-gray-400 text-sm">Active</p>
            <p className="text-3xl font-bold text-green-400 mt-1">
              {clients.filter(c => c.is_active).length}
            </p>
          </div>
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <p className="text-gray-400 text-sm">Inactive</p>
            <p className="text-3xl font-bold text-red-400 mt-1">
              {clients.filter(c => !c.is_active).length}
            </p>
          </div>
        </div>

        {/* Clients Table */}
        <div className="bg-gray-900 rounded-xl border border-gray-800">
          <div className="p-6 border-b border-gray-800">
            <h2 className="text-xl font-semibold">All Bots</h2>
          </div>

          {loading ? (
            <div className="p-8 text-center text-gray-400">Loading...</div>
          ) : clients.length === 0 ? (
            <div className="p-8 text-center text-gray-400">
              No bots yet.{" "}
              <Link href="/onboard" className="text-green-400 hover:underline">
                Add your first bot!
              </Link>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="text-gray-400 text-sm border-b border-gray-800">
                  <th className="text-left p-4">Business</th>
                  <th className="text-left p-4">Type</th>
                  <th className="text-left p-4">Bot Name</th>
                  <th className="text-left p-4">Status</th>
                  <th className="text-left p-4">Created</th>
                  <th className="text-left p-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {clients.map(client => (
                  <tr key={client.id} className="border-b border-gray-800 hover:bg-gray-800/50 transition">
                    <td className="p-4 font-medium">{client.business_name}</td>
                    <td className="p-4 text-gray-400 text-sm">{client.business_type}</td>
                    <td className="p-4 text-gray-400 text-sm">{client.bot_name}</td>
                    <td className="p-4">
                      <button
                        onClick={() => toggleStatus(client.id, client.is_active)}
                        disabled={togglingId === client.id}
                        className={`px-3 py-1 rounded-full text-xs font-medium transition ${
                          client.is_active
                            ? "bg-green-900 text-green-400 hover:bg-green-800"
                            : "bg-red-900 text-red-400 hover:bg-red-800"
                        }`}
                      >
                        {togglingId === client.id ? "..." : client.is_active ? "● Active" : "● Inactive"}
                      </button>
                    </td>
                    <td className="p-4 text-gray-400 text-sm">
                      {new Date(client.created_at).toLocaleDateString()}
                    </td>
                    <td className="p-4">
                      <div className="flex gap-2">
                        <Link
                          href={`/clients/${client.id}`}
                          className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium transition"
                        >
                          ✏️ Edit
                        </Link>
                        <Link
                          href={`/client-dashboard/${client.id}`}
                          className="bg-blue-900 hover:bg-blue-800 text-blue-300 px-3 py-1.5 rounded-lg text-xs font-medium transition"
                        >
                          📊 Leads
                        </Link>
                        <button
                          onClick={() => deleteClient(client.id, client.business_name)}
                          disabled={deletingId === client.id}
                          className="bg-red-900/60 hover:bg-red-900 text-red-400 px-3 py-1.5 rounded-lg text-xs font-medium transition"
                        >
                          {deletingId === client.id ? "..." : "🗑️"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </main>
  );
}
