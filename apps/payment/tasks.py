from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Payment, Webhook

@shared_task
def cleanup_old_payments():
    cuttoff_date = timezone.now() - timedelta(days=90)

    old_payments = Payment.objects.filter(
        created_at__lt = cuttoff_date,
        status_in = ['failed', 'cancelled']
    )

    deleted_payments = old.payments.delete()

    return {'deleted_payments': deleted_payments}

@shared_task
def cleanup_old_webhooks_events():
    cuttoff_date = timezone.now() - timedelta(days=30)

    old_events = Webhook.objects.filter(
        created_at__lt = cuttoff_date,
        status_in = ['processed', 'ignored']
    )

    deleted_events = webhooks.delete()

    return {'deleted_webhook_events': deleted_events}

@shared_task
def retry_failed_webhook_events():
    from .services import WebhookService

    retry_cutoff = timezone.now() - timedelta(hours=24)

    failed_events = Webhook.objects.filter(
        status = 'failed',
        created_at__lt = retry_cutoff,
    )[:50]

    processed_count = 0

    for event in failed_events:
        success = WebhookService.process_stripe_webhook(event_data)
        if success:
            event.mark_as_processed()
            processed_count += 1

    return {'reprocessed_events': processed_count}