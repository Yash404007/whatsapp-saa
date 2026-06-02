import requests

BASE_URL = "http://localhost:8000"

# ── STEP 1: Get all clients ──────────────────────────────────────────────────
response = requests.get(f"{BASE_URL}/admin/clients")
clients = response.json()

print("Your bots:")
for c in clients:
    print(f"  [{c['business_name']}]  id = {c['id']}")

print()

# ── STEP 2: Define services for each bot ────────────────────────────────────
# Find your client IDs from the output above and paste them here

CONSTRUCTDEV_ID = "9675a54e-9e45-4f3d-b2fc-eef282ea1fa4"
CONSTRUCTXR_ID  = "8d552147-558d-488e-9888-f29e0528ee0f"

# Edit these services to match what each business actually offers
constructdev_services = [
    {"name": "AR/VR Marketing",     "description": "Immersive experiential marketing"},
    {"name": "Video Renders",       "description": "High-quality video production"},
    {"name": "Photo Renders",       "description": "Photorealistic property visuals"},
    {"name": "Social Media",        "description": "Real estate social media content"},
]

constructxr_services = [
    {"name": "AR/VR Visualization", "description": "Immersive 3D experiences"},
    {"name": "BIM Modeling",        "description": "3D building information modeling"},
    {"name": "Site Planning",       "description": "Smart layout & analysis"},
    {"name": "XR Training",         "description": "AR/VR-powered team training"},
]

# ── STEP 3: Update both bots ─────────────────────────────────────────────────
for client_id, services, name in [
    (CONSTRUCTDEV_ID, constructdev_services, "Constructdev"),
    (CONSTRUCTXR_ID,  constructxr_services,  "ConstructXr"),
]:
    r = requests.put(
        f"{BASE_URL}/admin/clients/{client_id}",
        json={"services": services}
    )
    if r.status_code == 200:
        print(f"✅ {name} services updated successfully")
    else:
        print(f"❌ {name} failed: {r.status_code} — {r.text}")
