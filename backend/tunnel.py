from pyngrok import ngrok

ngrok.set_auth_token("3CIORzhQm2iEYHlmpgwGEW1fhde_2Uc82a4ACj1BSDNQSzHA3")
t = ngrok.connect(8000)
print(f"Public URL: {t.public_url}")
print(f"Webhook URL: {t.public_url}/webhook")
print("Tunnel is running... Press Enter to stop.")
input()