import json
import re
from groq import AsyncGroq
from groq import Groq


def generate_system_prompt(client_data: dict) -> str:
    groq_api_key = client_data.get("groq_api_key")
    if not groq_api_key:
        raise ValueError("Groq API key is required")

    client = Groq(api_key=groq_api_key)

    prompt = f"""You are an expert at creating AI chatbot system prompts for WhatsApp bots.

A business wants to deploy a WhatsApp AI receptionist bot. Based on the details below, 
create a detailed system prompt for their bot.

BUSINESS DETAILS:
- Business Name: {client_data.get('business_name')}
- Business Type: {client_data.get('business_type')}
- Description: {client_data.get('description')}
- Bot Name: {client_data.get('bot_name', 'Alex')}
- Bot Tone: {client_data.get('bot_tone', 'friendly')}
- Working Hours: {client_data.get('working_hours', 'Mon-Fri 9am-6pm')}
- Contact Phone: {client_data.get('contact_phone', '')}
- Contact Email: {client_data.get('contact_email', '')}
- Address: {client_data.get('address', '')}
- Fields to collect from users: {', '.join(client_data.get('collect_fields', []))}

REQUIREMENTS for the system prompt:
1. Define the bot's personality and name
2. List what information to collect from users
3. Define the conversation flow
4. Include business info (hours, contact, address)
5. Set strict rules (no medical/legal advice, stay on topic, etc)
6. Keep replies SHORT and conversational for WhatsApp
7. Handle both English and local language users

Return ONLY the system prompt text, nothing else. No explanation, no preamble."""

    result = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
        temperature=0.7,
    )

    return result.choices[0].message.content.strip()


async def get_ai_reply(
    history: list,
    user_message: str,
    system_prompt: str,
    groq_api_key: str,
    extra_context: str = ""
) -> str:
    try:
        client = AsyncGroq(api_key=groq_api_key)

        full_system = system_prompt
        full_system += "\n\nSTRICT WHATSAPP RULES:\n- Maximum 2 sentences per reply\n- Never list multiple things at once\n- Ask ONE question at a time\n- No bullet points or numbered lists\n- Keep it conversational and short"

        if extra_context:
            full_system += f"\n\nCONTEXT FOR THIS RESPONSE:\n{extra_context}"

        messages = [{"role": "system", "content": full_system}]
        for h in history:
            role = "assistant" if h["role"] == "model" else "user"
            messages.append({"role": role, "content": h["parts"][0]["text"]})
        messages.append({"role": "user", "content": user_message})

        result = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            max_tokens=150,
            temperature=0.7,
        )
        return result.choices[0].message.content.strip()
    except Exception as e:
        return "I'm having a technical issue. Please try again shortly."


async def extract_fields(
    user_message: str,
    fields: list,
    groq_api_key: str
) -> dict:
    try:
        from datetime import date
        today = date.today().isoformat()

        client = AsyncGroq(api_key=groq_api_key)

        prompt = f"""Extract the following fields from the user's message.
Return ONLY valid JSON — no explanation, no markdown fences.

Fields needed: {", ".join(fields)}
Today's date: {today}
User message: "{user_message}"

Rules:
- dates → YYYY-MM-DD format. For day names like "Monday" calculate next upcoming date from {today}
- times → HH:MM 24-hour format. "3pm"="15:00", "11am"="11:00"
- email → lowercase
- name → title-cased
- phone → digits only with country code
- If a field is absent → null

Output example: {{"name": "John Smith", "email": "j@g.com", "date": "2024-12-25", "time": "15:00"}}"""

        result = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0,
        )
        raw = result.choices[0].message.content.strip()
        clean = re.sub(r"```json|```", "", raw).strip()
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if not match:
            raise ValueError("No JSON found")
        return json.loads(match.group())
    except Exception as e:
        return {f: None for f in fields}