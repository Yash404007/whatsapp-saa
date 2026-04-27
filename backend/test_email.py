from dotenv import load_dotenv
load_dotenv()

from services.email_service import send_confirmation_email

send_confirmation_email(
    to_email="vedant.work01@gmail.com",
    business_name="ConstructXr",
    bot_name="Yash",
    collected_data={
        "name": "Test User",
        "email": "vedant.work01@gmail.com",
        "reason": "Website Design",
        "date": "2026-04-28",
        "time": "10:00"
    },
    gmail_sender="constructdevagency@gmail.com",
    gmail_password="docd lucg guld ewju"
)

print("Done!")