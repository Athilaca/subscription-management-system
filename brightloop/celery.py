import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "brightloop.settings.dev")

app = Celery("brightloop")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
