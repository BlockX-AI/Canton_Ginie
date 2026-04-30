"""Brevo transactional email service.

Sends OTP verification emails and other transactional messages.
API docs: https://developers.brevo.com/docs/send-a-transactional-email
"""

import httpx
import structlog
from typing import Optional

from config import get_settings

logger = structlog.get_logger()

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def _build_otp_html(otp: str, display_name: Optional[str] = None) -> str:
    """Build a beautiful HTML email for OTP verification."""
    greeting = f"Hi {display_name}," if display_name else "Hi there,"
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Your Ginie verification code</title>
</head>
<body style="margin:0; padding:0; background-color:#0a0a0a; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#0a0a0a; padding:40px 20px;">
    <tr>
      <td align="center">
        <table role="presentation" width="560" cellspacing="0" cellpadding="0" border="0" style="max-width:560px; width:100%;">
          <!-- Logo header -->
          <tr>
            <td align="center" style="padding-bottom:32px;">
              <div style="font-size:28px; font-weight:600; color:#a3e635; font-family:'EB Garamond',Georgia,serif;">Ginie</div>
              <div style="font-size:10px; letter-spacing:3px; color:#666; text-transform:uppercase; margin-top:4px;">Canton Network</div>
            </td>
          </tr>

          <!-- Main card -->
          <tr>
            <td style="background:linear-gradient(135deg,#1a1a1a 0%,#151515 100%); border:1px solid #2a2a2a; border-radius:16px; padding:40px;">
              <h1 style="margin:0 0 8px 0; color:#fafafa; font-size:24px; font-weight:600;">Verify your email</h1>
              <p style="margin:0 0 32px 0; color:#a0a0a0; font-size:15px; line-height:1.5;">
                {greeting}<br>
                Use this code to finish setting up your Ginie account:
              </p>

              <!-- OTP box -->
              <div style="background:#0a0a0a; border:1px solid #2a2a2a; border-radius:12px; padding:24px; text-align:center; margin-bottom:24px;">
                <div style="font-family:'SF Mono',Menlo,Consolas,monospace; font-size:36px; font-weight:700; letter-spacing:12px; color:#a3e635;">
                  {otp}
                </div>
              </div>

              <p style="margin:0; color:#666; font-size:13px; line-height:1.6;">
                This code expires in <strong style="color:#a0a0a0;">10 minutes</strong>.<br>
                If you didn't request this code, you can safely ignore this email.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td align="center" style="padding-top:24px;">
              <p style="margin:0; color:#555; font-size:12px; line-height:1.6;">
                Ginie Canton &middot; Daml Smart Contracts on Canton Network<br>
                <a href="https://canton.ginie.xyz" style="color:#a3e635; text-decoration:none;">canton.ginie.xyz</a>
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
""".strip()


def _build_welcome_html(display_name: str) -> str:
    """Welcome email after successful signup."""
    return f"""
<!DOCTYPE html>
<html>
<body style="margin:0; padding:40px 20px; background:#0a0a0a; font-family:-apple-system,sans-serif;">
  <table role="presentation" width="560" align="center" style="background:#151515; border:1px solid #2a2a2a; border-radius:16px; padding:40px;">
    <tr><td>
      <h1 style="color:#a3e635; margin:0 0 16px 0;">Welcome to Ginie, {display_name}! 🎉</h1>
      <p style="color:#a0a0a0; line-height:1.6;">
        Your account is ready. You just earned your first badge: <strong style="color:#a3e635;">🌱 Newcomer</strong>
      </p>
      <p style="color:#a0a0a0; line-height:1.6;">
        Start generating Daml contracts on Canton and unlock more badges as you build.
      </p>
      <a href="https://canton.ginie.xyz" style="display:inline-block; background:#a3e635; color:#0a0a0a; padding:12px 24px; border-radius:8px; text-decoration:none; font-weight:600; margin-top:16px;">
        Start Building →
      </a>
    </td></tr>
  </table>
</body>
</html>
""".strip()


async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    to_name: Optional[str] = None,
) -> bool:
    """Send email via Brevo API. Returns True on success."""
    settings = get_settings()
    
    if not settings.brevo_api_key:
        logger.warning("BREVO_API_KEY not configured — email not sent", to=to_email)
        return False
    
    payload = {
        "sender": {
            "name": settings.brevo_sender_name,
            "email": settings.brevo_sender_email,
        },
        "to": [{"email": to_email, "name": to_name or to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }
    
    headers = {
        "accept": "application/json",
        "api-key": settings.brevo_api_key,
        "content-type": "application/json",
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(BREVO_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            message_id = resp.json().get("messageId", "")
            logger.info("Email sent via Brevo", to=to_email, subject=subject, message_id=message_id)
            return True
    except httpx.HTTPStatusError as e:
        logger.error(
            "Brevo API error",
            to=to_email,
            status=e.response.status_code,
            body=e.response.text[:500],
        )
        return False
    except Exception as e:
        logger.exception("Failed to send email via Brevo", to=to_email, error=str(e))
        return False


async def send_otp_email(
    to_email: str,
    otp: str,
    display_name: Optional[str] = None,
) -> bool:
    """Send OTP verification email."""
    return await send_email(
        to_email=to_email,
        subject="Your Ginie verification code",
        html_content=_build_otp_html(otp, display_name),
        to_name=display_name,
    )


async def send_welcome_email(to_email: str, display_name: str) -> bool:
    """Send welcome email after successful signup."""
    return await send_email(
        to_email=to_email,
        subject=f"Welcome to Ginie, {display_name}! 🎉",
        html_content=_build_welcome_html(display_name),
        to_name=display_name,
    )
