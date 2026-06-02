from google_auth_oauthlib.flow import InstalledAppFlow
import sys

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

client_id = input("Paste your OAuth Client ID: ").strip()
client_secret = input("Paste your OAuth Client Secret: ").strip()

client_config = {
    "installed": {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uris": ["http://localhost"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
creds = flow.run_local_server(port=0)

print("\n✅ Add these 3 lines to your backend/.env:\n")
print(f"GOOGLE_OAUTH_CLIENT_ID={client_id}")
print(f"GOOGLE_OAUTH_CLIENT_SECRET={client_secret}")
print(f"GOOGLE_OAUTH_REFRESH_TOKEN={creds.refresh_token}")
