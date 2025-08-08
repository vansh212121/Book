# In your project's ROOT directory: celery_worker.py

from app.core.celery_app import celery_app

# This line is all that's needed. It makes the celery_app instance
# discoverable by the Celery command-line tool.
