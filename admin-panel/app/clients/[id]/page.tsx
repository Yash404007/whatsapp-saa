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
  contact_email: string;
  address: string;
  system_prompt: string;
  collect_fields: string[];
  services: { name: string; description: string }[] | null;
  use_calendar: boolean;
  use_sheets: boolean;
  use_email: boolean;
  is_active: boolean;
  created_at: string;
  google_account_email: string;
  sheets_id: string;
  calendar_id: string;
}

const ALL_FIELDS = [
  "name", "email", "phone", "company", "reason",
  "date", "time", "budget", "service_type",
  "project_description", "timeline", "location",
];

export default function ClientDetail() {
  const { id } = useParams();
  const router = useRouter();
  const [client, setClient] = useState<Client | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  // Edit mode
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<Partial<Client>>({});

  // Services edit
  const [editingServices, setEditingServices] = useState(false);
  const [services, setServices] = useState<{ name: string; description: string }[]>([]);
  const [savingServices, setSavingServices] = useState(false);

  const webhookUrl = `${process.env.NEXT_PUBLIC_WEBHOOK_BASE_URL}/webhook/${id}`;

  useEffect(() => {
    axios.get(`${process.env.NEXT_PUBLIC_API_URL}/admin/clients/${id}`)
      .then(res => {
        setClient(res.data);
        setServices(res.data.services || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [id]);

  const startEditing = () => {
    if (!client) return;
    setForm({
      business_name: client.business_name,
      business_type: client.business_type,
      description: client.description,
      bot_name: client.bot_name,
      bot_tone: client.bot_tone,
      working_hours: client.working_hours,
      contact_phone: client.contact_phone,
      contact_email: client.contact_email,
      address: client.address,
      collect_fields: client.collect_fields,
      is_active: client.is_active,
      google_account_email: client.google_account_email,
    });
    setEditing(true);
  };

  const saveEdits = async () => {
    setSaving(true);
    try {
      await axios.put(`${process.env.NEXT_PUBLIC_API_URL}/admin/clients/${id}`, form);
      setClient(prev => prev ? { ...prev, ...form } : prev);
      setEditing(false);
    } catch (err: any) {
      alert(`❌ Error: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const toggleField = (field: string) => {
    const current = (form.collect_fields || []) as string[];
    setForm(prev => ({
      ...prev,
      collect_fields: current.includes(field)
        ? current.filter(f => f !== field)
        : [...current, field],
    }));
  };

  const saveServices = async () => {
    setSavingServices(true);
    try {
      await axios.put(`${process.env.NEXT_PUBLIC_API_URL}/admin/clients/${id}`, { services });
      setClient(prev => prev ? { ...prev, services } : prev);
      setEditingServices(false);
    } catch (err: any) {
      alert(`❌ Error: ${err.message}`);
    } finally {
      setSavingServices(false);
    }
  };

  const regeneratePrompt = async () => {
    setRegenerating(true);
    try {
      const res = await axios.put(
        `${process.env.NEXT_PUBLIC_API_URL}/admin/clients/${id}/regenerate-prompt`
      );
      setClient(prev => prev ? { ...prev, system_prompt: res.data.system_prompt } : prev);
    } catch (err: any) {
      alert(`❌ Error: ${err.message}`);
    } finally {
      setRegenerating(false);
    }
  };

  const deleteClient = async () => {
    if (!confirm(`Delete "${client?.business_name}"? This cannot be undone.`)) return;
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
            <div className="flex gap-2">
              <Link
                href={`/client-dashboard/${id}`}
                className="bg-green-700 hover:bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
              >
                📊 Leads
              </Link>
              {!editing ? (
                <button
                  onClick={startEditing}
                  className="bg-blue-700 hover:bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
                >
                  ✏️ Edit
                </button>
              ) : (
                <>
                  <button
                    onClick={() => setEditing(false)}
                    className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={saveEdits}
                    disabled={saving}
                    className="bg-green-600 hover:bg-green-700 disabled:bg-gray-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
                  >
                    {saving ? "Saving..." : "💾 Save Changes"}
                  </button>
                </>
              )}
              <button
                onClick={deleteClient}
                disabled={deleting}
                className="bg-red-700 hover:bg-red-600 disabled:bg-gray-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
              >
                {deleting ? "Deleting..." : "🗑️ Delete"}
              </button>
            </div>
          </div>
        </div>

        {/* Webhook URL */}
        <div className="bg-gray-900 rounded-xl p-5 border border-green-800 mb-6">
          <p className="text-sm font-semibold text-green-400 mb-2">🔗 Webhook URL — paste in Meta Developer Console</p>
          <div className="flex items-center gap-3 bg-gray-800 rounded-lg p-3">
            <code className="text-green-300 text-sm flex-1 break-all">{webhookUrl}</code>
            <button
              onClick={() => { navigator.clipboard.writeText(webhookUrl); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
              className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition ${copied ? "bg-green-600 text-white" : "bg-gray-700 hover:bg-gray-600 text-white"}`}
            >
              {copied ? "✅ Copied!" : "📋 Copy"}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6">

          {/* Business Info — view or edit */}
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 col-span-2">
            <h2 className="text-lg font-semibold mb-4">📋 Business Info</h2>

            {!editing ? (
              <div className="grid grid-cols-2 gap-4">
                {[
                  ["Business Name", client.business_name],
                  ["Business Type", client.business_type],
                  ["Bot Name", client.bot_name],
                  ["Bot Tone", client.bot_tone],
                  ["Working Hours", client.working_hours || "—"],
                  ["Contact Phone", client.contact_phone || "—"],
                  ["Contact Email", client.contact_email || "—"],
                  ["Address", client.address || "—"],
                  ["Google Account Email", client.google_account_email || "—"],
                  ["Status", client.is_active ? "✅ Active" : "❌ Inactive"],
                  ["Created", new Date(client.created_at).toLocaleDateString()],
                ].map(([label, value]) => (
                  <div key={label}>
                    <p className="text-xs text-gray-400">{label}</p>
                    <p className="text-white text-sm mt-0.5">{value}</p>
                  </div>
                ))}
                <div className="col-span-2">
                  <p className="text-xs text-gray-400">Description</p>
                  <p className="text-white text-sm mt-0.5">{client.description || "—"}</p>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  {[
                    ["Business Name", "business_name", "e.g. Constructdev"],
                    ["Business Type", "business_type", "e.g. Digital Agency"],
                    ["Bot Name", "bot_name", "e.g. Alex"],
                    ["Working Hours", "working_hours", "e.g. Mon-Sat 10am-7pm"],
                    ["Contact Phone", "contact_phone", "+91-9876543210"],
                    ["Contact Email", "contact_email", "hello@business.com"],
                    ["Address", "address", "123 MG Road, Mumbai"],
                    ["Google Account Email", "google_account_email", "client@gmail.com — Sheet & Calendar shared here"],
                  ].map(([label, key, placeholder]) => (
                    <div key={key}>
                      <label className="text-xs text-gray-400">{label}</label>
                      <input
                        className="w-full bg-gray-800 rounded-lg p-2.5 mt-1 text-white border border-gray-700 focus:border-green-500 outline-none text-sm"
                        placeholder={placeholder}
                        value={(form as any)[key] || ""}
                        onChange={e => setForm(prev => ({ ...prev, [key]: e.target.value }))}
                      />
                    </div>
                  ))}

                  <div>
                    <label className="text-xs text-gray-400">Bot Tone</label>
                    <select
                      className="w-full bg-gray-800 rounded-lg p-2.5 mt-1 text-white border border-gray-700 focus:border-green-500 outline-none text-sm"
                      value={form.bot_tone || "friendly"}
                      onChange={e => setForm(prev => ({ ...prev, bot_tone: e.target.value }))}
                    >
                      <option value="friendly">Friendly</option>
                      <option value="professional">Professional</option>
                      <option value="casual">Casual</option>
                      <option value="formal">Formal</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="text-xs text-gray-400">Description</label>
                  <textarea
                    className="w-full bg-gray-800 rounded-lg p-2.5 mt-1 text-white border border-gray-700 focus:border-green-500 outline-none text-sm h-24"
                    placeholder="Describe what this bot does..."
                    value={form.description || ""}
                    onChange={e => setForm(prev => ({ ...prev, description: e.target.value }))}
                  />
                </div>

                <div>
                  <label className="text-xs text-gray-400 block mb-2">Status</label>
                  <button
                    type="button"
                    onClick={() => setForm(prev => ({ ...prev, is_active: !prev.is_active }))}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                      form.is_active ? "bg-green-700 text-white" : "bg-gray-700 text-gray-300"
                    }`}
                  >
                    {form.is_active ? "✅ Active" : "❌ Inactive"} — click to toggle
                  </button>
                </div>

                <div>
                  <label className="text-xs text-gray-400 block mb-2">Fields to Collect</label>
                  <div className="flex flex-wrap gap-2">
                    {ALL_FIELDS.map(field => (
                      <button
                        key={field}
                        type="button"
                        onClick={() => toggleField(field)}
                        className={`px-3 py-1 rounded-full text-xs font-medium transition ${
                          (form.collect_fields || []).includes(field)
                            ? "bg-green-700 text-white"
                            : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                        }`}
                      >
                        {field}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Services */}
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 col-span-2">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">🛎️ Services</h2>
              {!editingServices ? (
                <button
                  onClick={() => setEditingServices(true)}
                  className="text-sm bg-gray-700 hover:bg-gray-600 text-white px-4 py-1.5 rounded-lg transition"
                >
                  ✏️ Edit
                </button>
              ) : (
                <div className="flex gap-2">
                  <button onClick={() => { setEditingServices(false); setServices(client.services || []); }}
                    className="text-sm bg-gray-700 hover:bg-gray-600 text-white px-4 py-1.5 rounded-lg transition">
                    Cancel
                  </button>
                  <button onClick={saveServices} disabled={savingServices}
                    className="text-sm bg-green-600 hover:bg-green-700 disabled:bg-gray-700 text-white px-4 py-1.5 rounded-lg transition">
                    {savingServices ? "Saving..." : "💾 Save"}
                  </button>
                </div>
              )}
            </div>

            {!editingServices ? (
              (!client.services || client.services.length === 0) ? (
                <p className="text-gray-500 text-sm italic">No services — bot goes straight to lead collection.</p>
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  {client.services.map((svc, i) => (
                    <div key={i} className="bg-gray-800 rounded-lg p-3">
                      <p className="text-white font-medium text-sm">{svc.name}</p>
                      {svc.description && <p className="text-gray-400 text-xs mt-1">{svc.description}</p>}
                    </div>
                  ))}
                </div>
              )
            ) : (
              <div className="space-y-3">
                {services.map((svc, i) => (
                  <div key={i} className="flex gap-2 items-start">
                    <div className="flex-1 space-y-2">
                      <input
                        className="w-full bg-gray-800 rounded-lg p-2 text-white border border-gray-700 focus:border-green-500 outline-none text-sm"
                        placeholder="Service name"
                        value={svc.name}
                        onChange={e => { const u = [...services]; u[i] = { ...u[i], name: e.target.value }; setServices(u); }}
                      />
                      <input
                        className="w-full bg-gray-800 rounded-lg p-2 text-white border border-gray-700 focus:border-green-500 outline-none text-sm"
                        placeholder="Short description"
                        value={svc.description}
                        onChange={e => { const u = [...services]; u[i] = { ...u[i], description: e.target.value }; setServices(u); }}
                      />
                    </div>
                    <button onClick={() => setServices(services.filter((_, idx) => idx !== i))}
                      className="text-red-400 hover:text-red-300 text-lg mt-1 px-1">✕</button>
                  </div>
                ))}
                <button onClick={() => setServices([...services, { name: "", description: "" }])}
                  className="text-sm bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg transition">
                  + Add Service
                </button>
              </div>
            )}
          </div>

          {/* Integrations */}
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <h2 className="text-lg font-semibold mb-4">🔌 Integrations</h2>
            <div className="space-y-3">
              {[
                ["📧 Email", client.use_email],
                ["📅 Calendar", client.use_calendar],
                ["📊 Sheets", client.use_sheets],
              ].map(([label, enabled]) => (
                <div key={label as string} className="flex items-center justify-between">
                  <span className="text-gray-300 text-sm">{label as string}</span>
                  <span className={`px-2 py-1 rounded-full text-xs ${enabled ? "bg-green-900 text-green-400" : "bg-gray-700 text-gray-400"}`}>
                    {enabled ? "Enabled" : "Disabled"}
                  </span>
                </div>
              ))}
              <div className="border-t border-gray-700 pt-3 mt-3 space-y-2">
                <div>
                  <p className="text-xs text-gray-400">Google Account Email</p>
                  <p className="text-sm text-white mt-0.5">{client.google_account_email || "—"}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">Sheets ID</p>
                  <p className="text-xs text-green-400 font-mono mt-0.5 break-all">{client.sheets_id || "Not set"}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">Calendar ID</p>
                  <p className="text-xs text-blue-400 font-mono mt-0.5 break-all">{client.calendar_id || "Not set"}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Collected Fields */}
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <h2 className="text-lg font-semibold mb-4">📝 Fields to Collect</h2>
            {client.collect_fields?.length ? (
              <div className="flex flex-wrap gap-2">
                {client.collect_fields.map(field => (
                  <span key={field} className="bg-green-900 text-green-400 px-3 py-1 rounded-full text-xs">{field}</span>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-sm italic">No fields configured</p>
            )}
          </div>

          {/* System Prompt */}
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 col-span-2">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">🤖 AI System Prompt</h2>
              <button onClick={regeneratePrompt} disabled={regenerating}
                className="text-sm bg-blue-700 hover:bg-blue-600 disabled:bg-gray-700 text-white px-4 py-1.5 rounded-lg transition">
                {regenerating ? "Regenerating..." : "🔄 Regenerate"}
              </button>
            </div>
            <pre className="text-gray-300 text-sm whitespace-pre-wrap bg-gray-800 rounded-lg p-4 max-h-64 overflow-y-auto">
              {client.system_prompt || "No prompt generated yet."}
            </pre>
          </div>

        </div>
      </div>
    </main>
  );
}
