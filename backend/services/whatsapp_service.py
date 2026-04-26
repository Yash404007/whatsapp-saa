import httpx
from loguru import logger


async def send_message(phone: str, message: str, access_token: str, phone_number_id: str):
    """Send a WhatsApp message to a phone number."""
    url = f"https://graph.facebook.com/v25.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message}
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                logger.info(f"✅ Message sent to {phone}")
            else:
                logger.error(f"❌ Failed to send message: {response.text}")
    except Exception as e:
        logger.error(f"❌ WhatsApp send error: {str(e)}")


def parse_incoming(data: dict) -> tuple:
    """Extract phone number and message text from Meta webhook payload."""
    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        # Get phone number ID to identify client
        phone_number_id = value["metadata"]["phone_number_id"]

        messages = value.get("messages", [])
        if not messages:
            return None, None, phone_number_id

        message = messages[0]
        phone = message["from"]
        text = message.get("text", {}).get("body", "")

        return phone, text, phone_number_id

    except Exception as e:
        logger.error(f"❌ Failed to parse webhook: {str(e)}")
        return None, None, None