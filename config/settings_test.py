from .settings import *

# Все інше береться з .env автоматично
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
CELERY_TASK_ALWAYS_EAGER = True