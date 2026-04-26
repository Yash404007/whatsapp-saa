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

  useEffect(() => {
    axios.get(`${process.env.NEXT_PUBLIC_API_URL}/admin/clients`)
      .then(res => {
        setClients(res.data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

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
            + Add New Client
          </Link>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <p className="text-gray-400 text-sm">Total Clients</p>
            <p className="text-3xl font-bold text-white mt-1">{clients.length}</p>
          </div>
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <p className="text-gray-400 text-sm">Active Bots</p>
            <p className="text-3xl font-bold text-green-400 mt-1">
              {clients.filter(c => c.is_active).length}
            </p>
          </div>
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <p className="text-gray-400 text-sm">Inactive Bots</p>
            <p className="text-3xl font-bold text-red-400 mt-1">
              {clients.filter(c => !c.is_active).length}
            </p>
          </div>
        </div>

        {/* Clients Table */}
        <div className="bg-gray-900 rounded-xl border border-gray-800">
          <div className="p-6 border-b border-gray-800">
            <h2 className="text-xl font-semibold">All Clients</h2>
          </div>
          {loading ? (
            <div className="p-8 text-center text-gray-400">Loading...</div>
          ) : clients.length === 0 ? (
            <div className="p-8 text-center text-gray-400">
              No clients yet. <Link href="/onboard" className="text-green-400 hover:underline">Add your first client!</Link>
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
                  <tr key={client.id} className="border-b border-gray-800 hover:bg-gray-800 transition">
                    <td className="p-4 font-medium">{client.business_name}</td>
                    <td className="p-4 text-gray-400">{client.business_type}</td>
                    <td className="p-4 text-gray-400">{client.bot_name}</td>
                    <td className="p-4">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        client.is_active
                          ? "bg-green-900 text-green-400"
                          : "bg-red-900 text-red-400"
                      }`}>
                        {client.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="p-4 text-gray-400 text-sm">
                      {new Date(client.created_at).toLocaleDateString()}
                    </td>
                    <td className="p-4">
                      <Link
                        href={`/clients/${client.id}`}
                        className="text-blue-400 hover:underline text-sm"
                      >
                        View
                      </Link>
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