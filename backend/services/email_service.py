import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from loguru import logger


def send_confirmation_email(
    to_email: str,
    business_name: str,
    bot_name: str,
    collected_data: dict,
    gmail_sender: str,
    gmail_password: str,
):
    """Send confirmation email to user after lead is collected."""
    if not gmail_sender or not gmail_password:
        logger.warning("📧 Gmail credentials not set — skipping email")
        return

    try:
        subject = f"Thank you for contacting {business_name}!"

        # Build data rows
        rows = ""
        for key, value in collected_data.items():
            if value:
                rows += f"""
                <tr style="border-top:1px solid #e5e7eb;">
                    <td style="padding:10px;color:#6b7280;font-size:14px;text-transform:capitalize;">{key.replace('_', ' ')}</td>
                    <td style="padding:10px;color:#111827;font-size:14px;font-weight:500;">{value}</td>
                </tr>"""

        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;padding:30px 0;">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08);">

  <tr><td style="background:#16a34a;padding:28px 36px;text-align:center;">
    <h1 style="color:white;margin:0;font-size:22px;">✅ We received your details!</h1>
    <p style="color:#bbf7d0;margin:8px 0 0;font-size:14px;">{business_name}</p>
  </td></tr>

  <tr><td style="padding:32px 36px;">
    <p style="font-size:15px;color:#374151;margin:0 0 20px;">
      Hi there! Thanks for reaching out to <strong>{business_name}</strong>. 
      Here's a summary of what we received:
    </p>

    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:#f0fdf4;border-left:4px solid #16a34a;border-radius:4px;margin-bottom:24px;">
      {rows}
    </table>

    <p style="color:#6b7280;font-size:13px;line-height:1.6;">
      Our team will get back to you shortly. If you have any questions, 
      feel free to reach out to us directly.
    </p>
  </td></tr>

  <tr><td style="background:#f9fafb;padding:16px 36px;text-align:center;border-top:1px solid #e5e7eb;">
    <p style="margin:0;color:#9ca3af;font-size:12px;">{business_name} · Automated message via WhatsApp Bot</p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{business_name} <{gmail_sender}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_sender, gmail_password)
            server.sendmail(gmail_sender, to_email, msg.as_string())

        logger.info(f"📧 Confirmation email sent to {to_email}")

    except Exception as e:
        logger.error(f"❌ Email error: {str(e)}")