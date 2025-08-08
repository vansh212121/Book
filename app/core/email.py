# In a new file: app/core/email.py

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

logger = logging.getLogger(__name__)


def _send_email_sync(email_to: str, subject: str, html_content: str):
    """
    A robust, synchronous function to send an email using Python's smtplib.
    This is designed to be called from a synchronous environment like a Celery worker.
    """
    msg = MIMEMultipart()
    msg["From"] = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"
    msg["To"] = email_to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_content, "html"))

    try:
        # Connect to the SMTP server with a timeout to prevent hanging.
        with smtplib.SMTP(
            settings.MAIL_SERVER, settings.MAIL_PORT, timeout=15
        ) as server:
            server.starttls()  # Upgrade the connection to a secure one
            server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            server.send_message(msg)
        logger.info(f"Email sent successfully to {email_to}")
    except Exception as e:
        logger.error(f"Failed to send email to {email_to}: {e}", exc_info=True)
        # Re-raising the exception is important so Celery knows the task failed.
        raise


def send_password_reset_email_sync(email_to: str, token: str):
    """Builds and sends the password reset email synchronously."""
    reset_url = (
        f"http://localhost:8000/reset-password?token={token}"  # Assume a frontend URL
    )
    html_content = f"""
    <html><body>
        <h1>Reset Your Password</h1>
        <p>You requested a password reset. Please click the link below to set a new password:</p>
        <a href="{reset_url}">Reset My Password</a>
        <p>This link will expire in 1 hour.</p>
    </body></html>
    """
    _send_email_sync(email_to, "Reset Your Bookly Password", html_content)


def send_verification_email_sync(email_to: str, token: str):
    """Builds and sends the verification email synchronously."""
    verification_url = f"http://localhost:8000/verify-email?token={token}"
    html_content = f"""
    <html><body>
        <h1>Welcome to Bookly!</h1>
        <p>Please click the link below to verify your account:</p>
        <a href="{verification_url}">Verify My Account</a>
        <p>This link will expire in 24 hours.</p>
    </body></html>
    """
    _send_email_sync(email_to, "Verify Your Bookly Account", html_content)


def send_welcome_email_sync(email_to: str, first_name: str):
    """Builds and sends the welcome email synchronously."""
    html_content = f"""
    <html><body>
        <h1>Welcome to Bookly, {first_name}!</h1>
        <p>We're thrilled to have you join our community of book lovers.</p>
        <p>You can now start reviewing books, creating reading lists, and connecting with other readers.</p>
        <p>Happy reading!</p>
        <p>- The Bookly Team</p>
    </body></html>
    """
    _send_email_sync(email_to, f"Welcome to Bookly, {first_name}!", html_content)


def send_email_change_confirmation_sync(email_to: str, token: str):
    """Builds and sends the email change confirmation email synchronously."""
    confirmation_url = f"http://localhost:3000/confirm-email-change?token={token}"  # Assume a frontend URL
    html_content = f"""
    <html><body>
        <h1>Confirm Your New Email Address</h1>
        <p>You requested to change your email address for your Bookly account. Please click the link below to confirm this change:</p>
        <a href="{confirmation_url}">Confirm New Email</a>
        <p>If you did not request this change, you can safely ignore this email.</p>
        <p>This link will expire in 1 hour.</p>
    </body></html>
    """
    _send_email_sync(
        email_to, "Confirm Your New Email Address for Bookly", html_content
    )
