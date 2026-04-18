"""Email sending via Gmail SMTP."""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", SMTP_USER)


def send_email(to: str, subject: str, html_body: str, text_body: str = "") -> None:
    """Send an email via Gmail SMTP (TLS). Raises on failure."""
    if not SMTP_USER or not SMTP_PASSWORD:
        raise RuntimeError("SMTP credentials not configured. Set SMTP_USER and SMTP_PASSWORD in .env")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Fridge Observer <{EMAIL_FROM}>"
    msg["To"] = to

    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(EMAIL_FROM, to, msg.as_string())

    logger.info("Email sent to %s: %s", to, subject)


def send_otp_email(to: str, display_name: str, otp_code: str) -> None:
    """Send the OTP verification email."""
    subject = f"{otp_code} is your Fridge Observer verification code"

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
</head>
<body style="margin:0;padding:0;background:#FAFAF8;font-family:'Inter',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#FAFAF8;padding:40px 20px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#2d5a3d,#4A7C59);padding:32px;text-align:center;">
              <div style="font-size:40px;margin-bottom:8px;">❄️</div>
              <h1 style="color:#ffffff;font-size:22px;font-weight:700;margin:0;letter-spacing:-0.3px;">Fridge Observer</h1>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:36px 32px;">
              <p style="font-size:16px;color:#1A1A18;margin:0 0 8px;">Hi {display_name},</p>
              <p style="font-size:15px;color:#6B6860;line-height:1.6;margin:0 0 28px;">
                Use the code below to verify your email address and complete your Fridge Observer sign up.
              </p>

              <!-- OTP Code -->
              <div style="background:#EBF3EE;border:2px dashed #4A7C59;border-radius:12px;padding:24px;text-align:center;margin-bottom:28px;">
                <div style="font-size:40px;font-weight:700;letter-spacing:10px;color:#2d5a3d;font-family:'Courier New',monospace;">
                  {otp_code}
                </div>
              </div>

              <p style="font-size:13.5px;color:#A8A59E;line-height:1.6;margin:0 0 8px;">
                ⏰ This code expires in <strong>10 minutes</strong>.
              </p>
              <p style="font-size:13.5px;color:#A8A59E;line-height:1.6;margin:0;">
                If you didn't create a Fridge Observer account, you can safely ignore this email.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#F4F3EF;padding:20px 32px;text-align:center;border-top:1px solid #E8E6E0;">
              <p style="font-size:12px;color:#A8A59E;margin:0;">
                Fridge Observer · Smart food tracking to reduce waste
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    text_body = f"""Hi {display_name},

Your Fridge Observer verification code is:

  {otp_code}

This code expires in 10 minutes.

If you didn't create a Fridge Observer account, ignore this email.
"""

    send_email(to, subject, html_body, text_body)
