import os

files = [
    'main.py', 'database.py', 'config.py',
    'routers/admin.py', 'routers/webhook.py', 'routers/dashboard.py',
    'models/client.py', 'models/conversation.py',
    'services/ai_service.py', 'services/bot_engine.py',
    'services/whatsapp_service.py', 'services/calendar_service.py',
    'services/sheets_service.py', 'services/email_service.py',
]

for f in files:
    with open(f, 'w', encoding='utf-8') as file:
        file.write('')
    print(f'✅ Created: {f}')

print('\nAll files created cleanly!')