"""Email service for sending verification emails."""

import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@hc-ai.com")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


def send_verification_email(email: str, token: str) -> bool:
    """
    Send email verification link to user.
    
    Args:
        email: Recipient email address
        token: Verification token
        
    Returns:
        True if email sent successfully, False otherwise
    """
    if not SENDGRID_API_KEY:
        print(f"[EMAIL] SENDGRID_API_KEY not set. Would send verification email to {email}")
        print(f"[EMAIL] Verification URL: {FRONTEND_URL}/verify?token={token}")
        return True  # Return True in dev mode for testing
    
    verify_url = f"{FRONTEND_URL}/verify?token={token}"
    
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=email,
        subject="Verify Your Email - HC AI",
        html_content=f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #333;">Welcome to HC AI!</h2>
            <p>Please verify your email address to complete your registration.</p>
            <p>
                <a href="{verify_url}" 
                   style="display: inline-block; padding: 12px 24px; background-color: #4CAF50; 
                          color: white; text-decoration: none; border-radius: 4px;">
                    Verify Email
                </a>
            </p>
            <p style="color: #666;">Or copy this link into your browser:</p>
            <p style="word-break: break-all; color: #666;">{verify_url}</p>
            <p style="color: #999; font-size: 12px; margin-top: 24px;">
                This link expires in 24 hours.
                <br>
                If you didn't create an account, please ignore this email.
            </p>
        </div>
        """
    )
    
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        return response.status_code == 202
    except Exception as e:
        print(f"[EMAIL] Error sending verification email: {e}")
        return False
