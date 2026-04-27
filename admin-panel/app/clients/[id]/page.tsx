"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import axios from "axios";
import Link from "next/link";

interface Client {
  id: string;
  business_name: string;
  business_type: string;
  description: string;
  bot_name: string;
  bot_tone: string;
  working_hours: string;
  contact_phone: string;
  system_prompt: string;
  collect_fields: string[];
  use_calendar: boolean;
  use_sheets: boolean;
  use_email: boolean;
  is_active: boolean;
  created_at: string;
}

export default function ClientDetail() {
  const { id } = useParams();
  const router = useRouter();
  const [client, setClient] = useState<Client | null>(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [copied, setCopied] = useState(false);

  const webhookUrl = `${process.env.NEXT_PUBLIC_WEBHOOK_BASE_URL}/webhook/${id}`;

  useEffect(() => {
    axios.get(`${process.env.NEXT_PUBLIC_API_URL}/admin/clients/${id}`)
      .then(res => {
        setClient(res.data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [id]);

  const copyWebhook = () => {
    navigator.clipboard.writeText(webhookUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const regeneratePrompt = async () => {
    setRegenerating(true);
    try {
      const res = await axios.put(
        `${process.env.NEXT_PUBLIC_API_URL}/admin/clients/${id}/regenerate-prompt`
      );
      setClient(prev => prev ? { ...prev, system_prompt: res.data.system_prompt } : prev);
      alert("✅ System prompt regenerated!");
    } catch (err: any) {
      alert(`❌ Error: ${err.message}`);
    } finally {
      setRegenerating(false);
    }
  };

  const deleteClient = async () => {
    if (!confirm("Are you sure you want to delete this client?")) return;
    setDeleting(true);
    try {
      await axios.delete(`${process.env.NEXT_PUBLIC_API_URL}/admin/clients/${id}`);
      router.push("/dashboard");
    } catch (err: any) {
      alert(`❌ Error: ${err.message}`);
      setDeleting(false);
    }
  };

  if (loading) return (
    <main className="min-h-screen bg-gray-950 flex items-center justify-center">
      <p className="text-gray-400">Loading...</p>
    </main>
  );

  if (!client) return (
    <main className="min-h-screen bg-gray-950 flex items-center justify-center">
      <p className="text-red-400">Client not found</p>
    </main>
  );

  return (
    <main className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-4xl mx-auto">

        {/* Header */}
        <div className="mb-8">
          <Link href="/dashboard" className="text-gray-400 hover:text-white text-sm mb-2 block">
            ← Back to Dashboard
          </Link>
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold">{client.business_name}</h1>
              <p className="text-gray-400 mt-1">{client.business_type}</p>
            </div>
            <div className="flex gap-3">
              <Link
                href={`/client-dashboard/${id}`}
                className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
              >
                📊 View Dashboard
              </Link>
              <button
                onClick={regeneratePrompt}
                disabled={regenerating}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
              >
                {regenerating ? "Regenerating..." : "🔄 Regenerate Prompt"}
              </button>
              <button
                onClick={deleteClient}
                disabled={deleting}
                className="bg-red-600 hover:bg-red-700 disabled:bg-gray-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
              >
                {deleting ? "Deleting..." : "🗑️ Delete"}
              </button>
            </div>
          </div>
        </div>

        {/* Webhook URL Box */}
        <div className="bg-gray-900 rounded-xl p-5 border border-green-800 mb-6">
          <p className="text-sm font-semibold text-green-400 mb-3">
            🔗 WhatsApp Webhook URL — Paste this in Meta Developer Console
          </p>
          <div className="flex items-center gap-3 bg-gray-800 rounded-lg p-3">
            <code className="text-green-300 text-sm flex-1 break-all">
              {webhookUrl}
            </code>
            <button
              onClick={copyWebhook}
              className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition ${
                copied
                  ? "bg-green-600 text-white"
                  : "bg-gray-700 hover:bg-gray-600 text-white"
              }`}
            >
              {copied ? "✅ Copied!" : "📋 Copy"}
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            Use the <span className="text-gray-300">wa_verify_token</span> you set as the Verify Token in Meta
          </p>
        </div>

        <div className="grid grid-cols-2 gap-6">

          {/* Business Info */}
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <h2 className="text-lg font-semibold mb-4">📋 Business Info</h2>
            <div className="space-y-3">
              <div>
                <p className="text-xs text-gray-400">Bot Name</p>
                <p className="text-white">{client.bot_name}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Bot Tone</p>
                <p className="text-white capitalize">{client.bot_tone}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Working Hours</p>
                <p className="text-white">{client.working_hours || "Not set"}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Contact Phone</p>
                <p className="text-white">{client.contact_phone || "Not set"}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Status</p>
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                  client.is_active
                    ? "bg-green-900 text-green-400"
                    : "bg-red-900 text-red-400"
                }`}>
                  {client.is_active ? "Active" : "Inactive"}
                </span>
              </div>
              <div>
                <p className="text-xs text-gray-400">Created</p>
                <p className="text-white">{new Date(client.created_at).toLocaleDateString()}</p>
              </div>
            </div>
          </div>

          {/* Integrations */}
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <h2 className="text-lg font-semibold mb-4">🔌 Integrations</h2>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-gray-300">📧 Email</span>
                <span className={`px-2 py-1 rounded-full text-xs ${
                  client.use_email ? "bg-green-900 text-green-400" : "bg-gray-700 text-gray-400"
                }`}>
                  {client.use_email ? "Enabled" : "Disabled"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-300">📅 Calendar</span>
                <span className={`px-2 py-1 rounded-full text-xs ${
                  client.use_calendar ? "bg-green-900 text-green-400" : "bg-gray-700 text-gray-400"
                }`}>
                  {client.use_calendar ? "Enabled" : "Disabled"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-300">📊 Sheets</span>
                <span className={`px-2 py-1 rounded-full text-xs ${
                  client.use_sheets ? "bg-green-900 text-green-400" : "bg-gray-700 text-gray-400"
                }`}>
                  {client.use_sheets ? "Enabled" : "Disabled"}
                </span>
              </div>
            </div>

            <h2 className="text-lg font-semibold mt-6 mb-4">📝 Fields to Collect</h2>
            <div className="flex flex-wrap gap-2">
              {client.collect_fields?.map(field => (
                <span key={field} className="bg-green-900 text-green-400 px-3 py-1 rounded-full text-xs">
                  {field}
                </span>
              ))}
            </div>
          </div>

          {/* System Prompt */}
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 col-span-2">
            <h2 className="text-lg font-semibold mb-4">🤖 AI Generated System Prompt</h2>
            <pre className="text-gray-300 text-sm whitespace-pre-wrap bg-gray-800 rounded-lg p-4 max-h-64 overflow-y-auto">
              {client.system_prompt || "No system prompt generated yet."}
            </pre>
          </div>

        </div>
      </div>
    </main>
  );
}