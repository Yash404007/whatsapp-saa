"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import axios from "axios";

export default function OnboardClient() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    business_name: "",
    business_type: "",
    description: "",
    bot_name: "",
    bot_tone: "friendly",
    working_hours: "",
    contact_phone: "",
    contact_email: "",
    address: "",
    collect_fields: [] as string[],
    services: [] as { name: string; description: string }[],
    wa_phone_id: "",
    wa_access_token: "",
    wa_verify_token: "",
    use_calendar: false,
    use_sheets: false,
    use_email: false,
    gmail_sender: "",
    gmail_password: "",
    google_account_email: "",
    groq_api_key: "",
    dashboard_username: "",
    dashboard_password: "",
  });

  const addService = () =>
    setForm(prev => ({ ...prev, services: [...prev.services, { name: "", description: "" }] }));

  const removeService = (i: number) =>
    setForm(prev => ({ ...prev, services: prev.services.filter((_, idx) => idx !== i) }));

  const updateService = (i: number, field: "name" | "description", value: string) =>
    setForm(prev => {
      const updated = [...prev.services];
      updated[i] = { ...updated[i], [field]: value };
      return { ...prev, services: updated };
    });

  const fieldOptions = [
    "name", "email", "phone", "company", "reason",
    "date", "time", "budget", "service_type",
    "project_description", "timeline", "location"
  ];

  const toggleField = (field: string) => {
    setForm(prev => ({
      ...prev,
      collect_fields: prev.collect_fields.includes(field)
        ? prev.collect_fields.filter(f => f !== field)
        : [...prev.collect_fields, field]
    }));
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const res = await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL}/admin/clients`,
        form
      );
      alert(`✅ Client created! Bot ID: ${res.data.client_id}`);
      router.push("/dashboard");
    } catch (err: any) {
      alert(`❌ Error: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-2xl mx-auto">

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold">➕ Add New Client</h1>
          <p className="text-gray-400 mt-1">Fill in the details and AI will configure the bot automatically</p>
        </div>

        {/* Step Indicator */}
        <div className="flex gap-2 mb-8">
          {[1, 2, 3].map(s => (
            <div key={s} className={`flex-1 h-2 rounded-full ${step >= s ? "bg-green-500" : "bg-gray-700"}`} />
          ))}
        </div>

        {/* STEP 1 — Business Info */}
        {step === 1 && (
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 space-y-4">
            <h2 className="text-xl font-semibold mb-4">Step 1 — Business Info</h2>

            <div>
              <label className="text-sm text-gray-400">Business Name *</label>
              <input
                className="w-full bg-gray-800 rounded-lg p-3 mt-1 text-white border border-gray-700 focus:border-green-500 outline-none"
                placeholder="e.g. Dr. Sharma's Clinic"
                value={form.business_name}
                onChange={e => setForm({...form, business_name: e.target.value})}
              />
            </div>

            <div>
              <label className="text-sm text-gray-400">Business Type *</label>
              <input
                className="w-full bg-gray-800 rounded-lg p-3 mt-1 text-white border border-gray-700 focus:border-green-500 outline-none"
                placeholder="e.g. Medical Clinic, Tech Agency, Salon"
                value={form.business_type}
                onChange={e => setForm({...form, business_type: e.target.value})}
              />
            </div>

            <div>
              <label className="text-sm text-gray-400">Description * (tell the AI what the bot should do)</label>
              <textarea
                className="w-full bg-gray-800 rounded-lg p-3 mt-1 text-white border border-gray-700 focus:border-green-500 outline-none h-28"
                placeholder="e.g. A general physician clinic that books patient appointments via WhatsApp. Collect name, email, reason for visit, preferred date and time."
                value={form.description}
                onChange={e => setForm({...form, description: e.target.value})}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-gray-400">Bot Name</label>
                <input
                  className="w-full bg-gray-800 rounded-lg p-3 mt-1 text-white border border-gray-700 focus:border-green-500 outline-none"
                  placeholder="e.g. Priya, Alex"
                  value={form.bot_name}
                  onChange={e => setForm({...form, bot_name: e.target.value})}
                />
              </div>
              <div>
                <label className="text-sm text-gray-400">Bot Tone</label>
                <select
                  className="w-full bg-gray-800 rounded-lg p-3 mt-1 text-white border border-gray-700 focus:border-green-500 outline-none"
                  value={form.bot_tone}
                  onChange={e => setForm({...form, bot_tone: e.target.value})}
                >
                  <option value="friendly">Friendly</option>
                  <option value="professional">Professional</option>
                  <option value="casual">Casual</option>
                  <option value="formal">Formal</option>
                </select>
              </div>
            </div>

            <div>
              <label className="text-sm text-gray-400">Working Hours</label>
              <input
                className="w-full bg-gray-800 rounded-lg p-3 mt-1 text-white border border-gray-700 focus:border-green-500 outline-none"
                placeholder="e.g. Mon-Sat 10am-8pm"
                value={form.working_hours}
                onChange={e => setForm({...form, working_hours: e.target.value})}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-gray-400">Contact Phone</label>
                <input
                  className="w-full bg-gray-800 rounded-lg p-3 mt-1 text-white border border-gray-700 focus:border-green-500 outline-none"
                  placeholder="+91-9876543210"
                  value={form.contact_phone}
                  onChange={e => setForm({...form, contact_phone: e.target.value})}
                />
              </div>
              <div>
                <label className="text-sm text-gray-400">Contact Email</label>
                <input
                  className="w-full bg-gray-800 rounded-lg p-3 mt-1 text-white border border-gray-700 focus:border-green-500 outline-none"
                  placeholder="clinic@gmail.com"
                  value={form.contact_email}
                  onChange={e => setForm({...form, contact_email: e.target.value})}
                />
              </div>
            </div>

            <div>
              <label className="text-sm text-gray-400">Address</label>
              <input
                className="w-full bg-gray-800 rounded-lg p-3 mt-1 text-white border border-gray-700 focus:border-green-500 outline-none"
                placeholder="123 MG Road, Mumbai"
                value={form.address}
                onChange={e => setForm({...form, address: e.target.value})}
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm text-gray-400">Services You Offer</label>
                <button
                  type="button"
                  onClick={addService}
                  className="text-xs bg-green-700 hover:bg-green-600 text-white px-3 py-1 rounded-full transition"
                >
                  + Add Service
                </button>
              </div>
              {form.services.length === 0 && (
                <p className="text-xs text-gray-500 italic">No services added — bot will skip service selection and go straight to lead collection.</p>
              )}
              <div className="space-y-3">
                {form.services.map((svc, i) => (
                  <div key={i} className="flex gap-2 items-start">
                    <div className="flex-1 space-y-2">
                      <input
                        className="w-full bg-gray-800 rounded-lg p-2 text-white border border-gray-700 focus:border-green-500 outline-none text-sm"
                        placeholder={`Service name (e.g. AR/VR Marketing)`}
                        value={svc.name}
                        onChange={e => updateService(i, "name", e.target.value)}
                      />
                      <input
                        className="w-full bg-gray-800 rounded-lg p-2 text-white border border-gray-700 focus:border-green-500 outline-none text-sm"
                        placeholder={`Short description (e.g. Immersive 3D experiences)`}
                        value={svc.description}
                        onChange={e => updateService(i, "description", e.target.value)}
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => removeService(i)}
                      className="text-red-400 hover:text-red-300 text-lg mt-1 px-1"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <label className="text-sm text-gray-400 block mb-2">Fields to Collect from Users</label>
              <div className="flex flex-wrap gap-2">
                {fieldOptions.map(field => (
                  <button
                    key={field}
                    onClick={() => toggleField(field)}
                    className={`px-3 py-1 rounded-full text-sm font-medium transition ${
                      form.collect_fields.includes(field)
                        ? "bg-green-600 text-white"
                        : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                    }`}
                  >
                    {field}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={() => setStep(2)}
              disabled={!form.business_name || !form.business_type || !form.description}
              className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-700 disabled:text-gray-500 text-white py-3 rounded-lg font-semibold transition mt-4"
            >
              Next: WhatsApp Setup →
            </button>
          </div>
        )}

        {/* STEP 2 — WhatsApp & Integrations */}
        {step === 2 && (
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 space-y-4">
            <h2 className="text-xl font-semibold mb-4">Step 2 — WhatsApp & Integrations</h2>

            <div>
              <label className="text-sm text-gray-400">WhatsApp Phone Number ID *</label>
              <input
                className="w-full bg-gray-800 rounded-lg p-3 mt-1 text-white border border-gray-700 focus:border-green-500 outline-none"
                placeholder="1084786714714480"
                value={form.wa_phone_id}
                onChange={e => setForm({...form, wa_phone_id: e.target.value})}
              />
            </div>

            <div>
              <label className="text-sm text-gray-400">WhatsApp Access Token *</label>
              <input
                className="w-full bg-gray-800 rounded-lg p-3 mt-1 text-white border border-gray-700 focus:border-green-500 outline-none"
                placeholder="EAAxxxxx..."
                value={form.wa_access_token}
                onChange={e => setForm({...form, wa_access_token: e.target.value})}
              />
            </div>

            <div>
              <label className="text-sm text-gray-400">WhatsApp Verify Token *</label>
              <input
                className="w-full bg-gray-800 rounded-lg p-3 mt-1 text-white border border-gray-700 focus:border-green-500 outline-none"
                placeholder="any_random_string"
                value={form.wa_verify_token}
                onChange={e => setForm({...form, wa_verify_token: e.target.value})}
              />
            </div>

            <div>
              <label className="text-sm text-gray-400">Groq API Key *</label>
              <input
                className="w-full bg-gray-800 rounded-lg p-3 mt-1 text-white border border-gray-700 focus:border-green-500 outline-none"
                placeholder="gsk_xxxx..."
                value={form.groq_api_key}
                onChange={e => setForm({...form, groq_api_key: e.target.value})}
              />
            </div>

            {/* Google Account per bot */}
            <div className="border border-green-800/50 bg-green-950/20 rounded-lg p-4 space-y-3">
              <p className="text-sm font-semibold text-green-400">📊 Google Sheets & Calendar</p>
              <p className="text-xs text-gray-400">Each bot gets its own Sheet and Calendar. Enter the Gmail that should have access to this bot's data.</p>
              <input
                className="w-full bg-gray-800 rounded-lg p-3 text-white border border-gray-700 focus:border-green-500 outline-none"
                placeholder="client@gmail.com (Sheet + Calendar will be shared here)"
                value={form.google_account_email}
                onChange={e => setForm({...form, google_account_email: e.target.value})}
              />
              <p className="text-xs text-gray-500">Leave blank to use the platform master account only.</p>
            </div>

            <div className="border border-gray-700 rounded-lg p-4 space-y-3">
              <p className="text-sm font-medium text-gray-300">Optional Integrations</p>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.use_email}
                  onChange={e => setForm({...form, use_email: e.target.checked})}
                  className="w-4 h-4 accent-green-500"
                />
                <span className="text-sm text-gray-300">📧 Email Confirmation to Leads (Gmail SMTP)</span>
              </label>

              {form.use_email && (
                <div className="space-y-3 pl-7">
                  <p className="text-xs text-gray-500">Sends a confirmation email to leads after they complete the bot flow.</p>
                  <input
                    className="w-full bg-gray-800 rounded-lg p-3 text-white border border-gray-700 focus:border-green-500 outline-none"
                    placeholder="Gmail address to send FROM"
                    value={form.gmail_sender}
                    onChange={e => setForm({...form, gmail_sender: e.target.value})}
                  />
                  <input
                    className="w-full bg-gray-800 rounded-lg p-3 text-white border border-gray-700 focus:border-green-500 outline-none"
                    placeholder="Gmail App Password"
                    type="password"
                    value={form.gmail_password}
                    onChange={e => setForm({...form, gmail_password: e.target.value})}
                  />
                </div>
              )}
            </div>

            <div className="flex gap-3 mt-4">
              <button
                onClick={() => setStep(1)}
                className="flex-1 bg-gray-700 hover:bg-gray-600 text-white py-3 rounded-lg font-semibold transition"
              >
                ← Back
              </button>
              <button
                onClick={() => setStep(3)}
                className="flex-1 bg-green-600 hover:bg-green-700 text-white py-3 rounded-lg font-semibold transition"
              >
                Next: Dashboard Login →
              </button>
            </div>
          </div>
        )}

        {/* STEP 3 — Dashboard Login */}
        {step === 3 && (
          <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 space-y-4">
            <h2 className="text-xl font-semibold mb-4">Step 3 — Client Dashboard Login</h2>
            <p className="text-gray-400 text-sm">Create login credentials for the client to access their dashboard.</p>

            <div>
              <label className="text-sm text-gray-400">Dashboard Username</label>
              <input
                className="w-full bg-gray-800 rounded-lg p-3 mt-1 text-white border border-gray-700 focus:border-green-500 outline-none"
                placeholder="e.g. drsharma"
                value={form.dashboard_username}
                onChange={e => setForm({...form, dashboard_username: e.target.value})}
              />
            </div>

            <div>
              <label className="text-sm text-gray-400">Dashboard Password</label>
              <input
                type="password"
                className="w-full bg-gray-800 rounded-lg p-3 mt-1 text-white border border-gray-700 focus:border-green-500 outline-none"
                placeholder="Set a strong password"
                value={form.dashboard_password}
                onChange={e => setForm({...form, dashboard_password: e.target.value})}
              />
            </div>

            <div className="bg-gray-800 rounded-lg p-4 mt-2">
              <p className="text-sm text-gray-400 font-medium mb-2">📋 Summary</p>
              <p className="text-sm text-gray-300">Business: <span className="text-white">{form.business_name}</span></p>
              <p className="text-sm text-gray-300">Type: <span className="text-white">{form.business_type}</span></p>
              <p className="text-sm text-gray-300">Bot Name: <span className="text-white">{form.bot_name || "Alex"}</span></p>
              <p className="text-sm text-gray-300">Fields: <span className="text-white">{form.collect_fields.join(", ") || "none selected"}</span></p>
              <p className="text-sm text-gray-300">Email: <span className="text-white">{form.use_email ? "✅" : "❌"}</span></p>
              <p className="text-sm text-gray-300">Calendar: <span className="text-white">{form.use_calendar ? "✅" : "❌"}</span></p>
              <p className="text-sm text-gray-300">Sheets: <span className="text-white">{form.use_sheets ? "✅" : "❌"}</span></p>
            </div>

            <div className="flex gap-3 mt-4">
              <button
                onClick={() => setStep(2)}
                className="flex-1 bg-gray-700 hover:bg-gray-600 text-white py-3 rounded-lg font-semibold transition"
              >
                ← Back
              </button>
              <button
                onClick={handleSubmit}
                disabled={loading}
                className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-700 text-white py-3 rounded-lg font-semibold transition"
              >
                {loading ? "🤖 AI is generating bot..." : "🚀 Create Bot"}
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}