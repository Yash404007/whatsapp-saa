"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import axios from "axios";
import Link from "next/link";

interface Stats {
  total_leads: number;
  total_conversations: number;
  completed_conversations: number;
}

interface Lead {
  id: string;
  phone: string;
  data: Record<string, any>;
  status: string;
  created_at: string;
}

interface Conversation {
  id: string;
  phone: string;
  stage: string;
  is_complete: boolean;
  message_count: number;
  updated_at: string;
}

export default function ClientDashboard() {
  const { id } = useParams();
  const [stats, setStats] = useState<Stats | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeTab, setActiveTab] = useState<"leads" | "conversations">("leads");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const API = process.env.NEXT_PUBLIC_API_URL;
    Promise.all([
      axios.get(`${API}/dashboard/${id}/stats`),
      axios.get(`${API}/dashboard/${id}/leads`),
      axios.get(`${API}/dashboard/${id}/conversations`),
    ]).then(([statsRes, leadsRes, convsRes]) => {
      setStats(statsRes.data);
      setLeads(leadsRes.data);
      setConversations(convsRes.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [id]);

  if (loading) return (
    <main className="min-h-screen bg-gray-950 flex items-center justify-center">
      <p className="text-gray-400">Loading dashboard...</p>
    </main>
  );

  return (
    <main className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-6xl mx-auto">

        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <Link href="/dashboard" className="text-gray-400 hover:text-white text-sm mb-2 block">
              ← Back to Admin
            </Link>
            <h1 className="text-3xl font-bold">📊 Client Dashboard</h1>
            <p className="text-gray-400 mt-1">View leads and conversations</p>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <p className="text-gray-400 text-sm">Total Leads</p>
            <p className="text-3xl font-bold text-green-400 mt-1">{stats?.total_leads || 0}</p>
          </div>
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <p className="text-gray-400 text-sm">Total Conversations</p>
            <p className="text-3xl font-bold text-blue-400 mt-1">{stats?.total_conversations || 0}</p>
          </div>
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <p className="text-gray-400 text-sm">Completed</p>
            <p className="text-3xl font-bold text-purple-400 mt-1">{stats?.completed_conversations || 0}</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setActiveTab("leads")}
            className={`px-6 py-2 rounded-lg font-medium transition ${
              activeTab === "leads"
                ? "bg-green-600 text-white"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            🎯 Leads ({leads.length})
          </button>
          <button
            onClick={() => setActiveTab("conversations")}
            className={`px-6 py-2 rounded-lg font-medium transition ${
              activeTab === "conversations"
                ? "bg-blue-600 text-white"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            💬 Conversations ({conversations.length})
          </button>
        </div>

        {/* Leads Tab */}
        {activeTab === "leads" && (
          <div className="bg-gray-900 rounded-xl border border-gray-800">
            <div className="p-6 border-b border-gray-800">
              <h2 className="text-xl font-semibold">🎯 All Leads</h2>
            </div>
            {leads.length === 0 ? (
              <div className="p-8 text-center text-gray-400">
                No leads yet. Leads appear here when users complete the conversation.
              </div>
            ) : (
              <div className="divide-y divide-gray-800">
                {leads.map(lead => (
                  <div key={lead.id} className="p-6">
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <p className="font-medium text-white">
                          {lead.data?.name || "Unknown"}
                        </p>
                        <p className="text-gray-400 text-sm">{lead.phone}</p>
                      </div>
                      <div className="text-right">
                        <span className="bg-green-900 text-green-400 px-2 py-1 rounded-full text-xs">
                          {lead.status}
                        </span>
                        <p className="text-gray-400 text-xs mt-1">
                          {new Date(lead.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(lead.data || {}).map(([key, value]) => (
                        <span key={key} className="bg-gray-800 text-gray-300 px-3 py-1 rounded-lg text-xs">
                          <span className="text-gray-500">{key}:</span> {String(value)}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Conversations Tab */}
        {activeTab === "conversations" && (
          <div className="bg-gray-900 rounded-xl border border-gray-800">
            <div className="p-6 border-b border-gray-800">
              <h2 className="text-xl font-semibold">💬 All Conversations</h2>
            </div>
            {conversations.length === 0 ? (
              <div className="p-8 text-center text-gray-400">
                No conversations yet.
              </div>
            ) : (
              <table className="w-full">
                <thead>
                  <tr className="text-gray-400 text-sm border-b border-gray-800">
                    <th className="text-left p-4">Phone</th>
                    <th className="text-left p-4">Stage</th>
                    <th className="text-left p-4">Messages</th>
                    <th className="text-left p-4">Status</th>
                    <th className="text-left p-4">Last Active</th>
                  </tr>
                </thead>
                <tbody>
                  {conversations.map(conv => (
                    <tr key={conv.id} className="border-b border-gray-800 hover:bg-gray-800 transition">
                      <td className="p-4 font-medium">{conv.phone}</td>
                      <td className="p-4 text-gray-400 capitalize">{conv.stage}</td>
                      <td className="p-4 text-gray-400">{conv.message_count}</td>
                      <td className="p-4">
                        <span className={`px-2 py-1 rounded-full text-xs ${
                          conv.is_complete
                            ? "bg-green-900 text-green-400"
                            : "bg-yellow-900 text-yellow-400"
                        }`}>
                          {conv.is_complete ? "Completed" : "In Progress"}
                        </span>
                      </td>
                      <td className="p-4 text-gray-400 text-sm">
                        {new Date(conv.updated_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </main>
  );
}