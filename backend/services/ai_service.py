import json
import re
from groq import AsyncGroq
from groq import Groq


def generate_system_prompt(client_data: dict) -> str:
    groq_api_key = client_data.get("groq_api_key")
    if not groq_api_key:
        raise ValueError("Groq API key is required")

    client = Groq(api_key=groq_api_key)

    prompt = f"""Create a WhatsApp sales bot system prompt for this business:

Business: {client_data.get('business_name')}
Type: {client_data.get('business_type')}
Description: {client_data.get('description')}
Bot Name: {client_data.get('bot_name', 'Alex')}
Tone: {client_data.get('bot_tone', 'friendly')}
Hours: {client_data.get('working_hours', '')}
Phone: {client_data.get('contact_phone', '')}
Fields to collect: {', '.join(client_data.get('collect_fields', []))}

The bot must:
1. Be a warm confident sales consultant
2. Know the business services deeply
3. Answer FAQs naturally
4. Build trust through results and proof
5. Guide users toward booking

WhatsApp formatting rules:
- Use *text* for bold (NOT ** or * *)
- Use emojis naturally
- Keep replies under 5 lines
- Never use bullet points with asterisks like * item
- Use ✅ or • for lists

Return ONLY the system prompt."""

    result = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
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
        full_system += """

STRICT WHATSAPP RULES — NEVER BREAK THESE:
- Max 5 lines per reply
- Bold = *word* NOT ** word ** or * word *
- Lists use ✅ or • NOT asterisks
- Max 2 emojis per message
- ONE question per message only
- Never sound robotic
- Never use markdown headers like ##
- Short punchy sentences"""

        if extra_context:
            full_system += f"\n\nCONTEXT:\n{extra_context}"

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
        return "Having a small issue. Please try again! 🙏"


async def extract_fields(
    user_message: str,
    fields: list,
    groq_api_key: str
) -> dict:
    try:
        from datetime import date
        today = date.today().isoformat()

        client = AsyncGroq(api_key=groq_api_key)

        prompt = f"""Extract fields from message. Return ONLY valid JSON.

Fields: {", ".join(fields)}
Today: {today}
Message: "{user_message}"

Rules:
- dates → YYYY-MM-DD
- times → HH:MM 24hr
- email → lowercase
- name → Title Case
- null if not found

Example: {{"name": "John", "email": "j@g.com"}}"""

        result = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0,
        )
        raw = result.choices[0].message.content.strip()
        clean = re.sub(r"```json|```", "", raw).strip()
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if not match:
            raise ValueError("No JSON found")
        return json.loads(match.group())
    except Exception:
        return {f: None for f in fields}