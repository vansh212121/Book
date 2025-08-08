# In a new file: app/tasks/email_tasks.py

import logging
from app.core.celery_app import celery_app
from app.core import email

logger = logging.getLogger(__name__)


@celery_app.task
def send_password_reset_email_task(email_to: str, token: str):
    """
    A Celery task that calls the synchronous email function for password resets.
    """
    logger.info(f"Worker received task: send password reset email to {email_to}")
    try:
        email.send_password_reset_email_sync(email_to=email_to, token=token)
        logger.info(f"Successfully sent password reset email to {email_to}")
    except Exception as e:
        logger.error(
            f"Failed to send password reset email to {email_to}: {e}", exc_info=True
        )
        # Celery will automatically retry the task based on its configuration if it fails.


@celery_app.task
def send_verification_email_task(email_to: str, token: str):
    """
    A Celery task that calls the synchronous email function for verification.
    """
    logger.info(f"Worker received task: send verification email to {email_to}")
    try:
        email.send_verification_email_sync(email_to=email_to, token=token)
        logger.info(f"Successfully sent verification email to {email_to}")
    except Exception as e:
        logger.error(
            f"Failed to send verification email to {email_to}: {e}", exc_info=True
        )


@celery_app.task
def send_welcome_email_task(email_to: str, first_name: str):
    """A Celery task to send a welcome email."""
    logger.info(f"Worker received task: send welcome email to {email_to}")
    try:
        email.send_welcome_email_sync(email_to=email_to, first_name=first_name)
        logger.info(f"Successfully sent welcome email to {email_to}")
    except Exception as e:
        logger.error(f"Failed to send welcome email to {email_to}: {e}", exc_info=True)


@celery_app.task
def send_email_change_confirmation_task(email_to: str, token: str):
    """A Celery task to send an email change confirmation."""
    logger.info(f"Worker received task: send email change confirmation to {email_to}")
    try:
        email.send_email_change_confirmation_sync(email_to=email_to, token=token)
        logger.info(f"Successfully sent email change confirmation to {email_to}")
    except Exception as e:
        logger.error(
            f"Failed to send email change confirmation to {email_to}: {e}",
            exc_info=True,
        )
