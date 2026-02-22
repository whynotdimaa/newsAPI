from django.db import models
from django.conf import settings
from decimal import Decimal
from django.utils import timezone
from apps.subscribe.models import Subscription


class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('canceled', 'Canceled'),
        ('refunded', 'Refunded'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('manual', 'Manual'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    subscription = models.ForeignKey('subscribe.Subscription', on_delete=models.CASCADE, related_name='payments', null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default ='usd')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, default='stripe')

    stripe_payment_intent_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_session_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True)

    description = models.TextField(blank = True)
    metadata = models.JSONField(default = dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'payments'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['stripe_payment_intent_id']),
            models.Index(fields=['stripe_session_id']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'Payment {self.id} - {self.user.username} - ${self.amount} ({self.status})'


    @property
    def is_successful(self):
        '''Провіряє успішність платежу'''
        return self.status == 'succeeded'

    @property
    def is_pending(self):
        '''Провіряє чи очікує платіж обробки'''
        return self.status in ['pending', 'processing']

    @property
    def can_be_refunded(self):
        '''Провіряє чи можна вернути платіж'''

    def mark_as_succeeded(self):
        '''Помічає платіж як успішний'''
        self.status = 'succeeded'
        self.processed_at = timezone.now()
        self.save()

    def mark_as_failed(self):
        '''Помічає платіж як невдалий'''
        self.status = 'failed'
        self.processed_at = timezone.now()
        if reason:
            self.metadata['failure_reason'] = reason
        self.save()


class PaymentAttempt(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='attempts')
    stripe_charge_id = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=50)
    error_message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default = dict, blank=True)

    class Meta:
        db_table = 'payment_attempts'
        verbose_name = 'Payment Attempt'
        verbose_name_plural = 'Payment Attempts'
        ordering = ['-created_at']

    def __str__(self):
        return f"Attempt for Payment {self.payment.id} - {self.status} "

class Refund(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='refunds')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField(blank = True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    stripe_refund_id = models.CharField(max_length=255, null=True, blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_refunds')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'refunds'
        verbose_name = 'Refund'
        verbose_name_plural = 'Refunds'
        ordering = ['-created_at']

    def __str__(self):
        return f"Refund  {self.id} - {self.amount} for Payment {self.payment.id} "

    @property
    def is_partial(self):
        '''Перевіряє чи возврат частичний'''

    def process_refund(self):
        '''Обробляє возврат'''
        self.status = 'succeeded'
        self.processed_at = timezone.now()
        self.save()

class Webhook(models.Model):
    PROVIDER_CHOICES = [
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('failed', 'Failed'),
        ('ignored', 'Ignored')
    ]
    provider = models.CharField(max_length=10, choices=PROVIDER_CHOICES, default='stripe')
    event_id = models.CharField(max_length=255, null=True, blank=True)
    event_type = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    data = models.JSONField()
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank = True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'webhooks_events'
        verbose_name = 'Webhook Event'
        verbose_name_plural = 'Webhooks Events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['provider', 'event_type']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.provider} - {self.event_type} ({self.status})"

    def mark_as_processed(self):
        self.status = 'processed'
        self.processed_at = timezone.now()
        self.save()

    def mark_as_failed(self, error_message):
        self.status = 'failed'
        self.error_message = error_message
        self.processed_at = timezone.now()
        self.save()


