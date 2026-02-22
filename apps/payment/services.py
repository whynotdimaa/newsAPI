import stripe
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from typing import Dict, Optional, Tuple
import logging

from .models import Payment, PaymentAttempt, Webhook
from apps.subscribe.models import Subscription, SubscriptionHistory, SubscriptionPlan

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    '''Створення клієнта в Stripe'''

    @staticmethod
    def create_customer(user) -> Optional[str]:
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name = user.get_full_name() or user.username,
                metadata = {
                    'user_id' : user.id,
                    'username' : user.username,
                }
            )
            return customer.id
        except stripe.error.StripeError as e:
            logger.error(f'Error creating customer {e}')
            return None

    @staticmethod
    def create_checkout_session(payment: Payment, success_url: str, cancel_url: str) -> Optional[dict]:
        """Створює сесію Stripe checkout"""

        try:
            if not payment.stripe_customer_id:
                customer_id = StripeService.create_customer(payment.user)
                if customer_id:
                    payment.stripe_customer_id = customer_id
                    payment.save()

            session = stripe.checkout.Session.create(
                customer=payment.stripe_customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': payment.currency.lower(),
                        'product_data': {
                            'name': f'Subscription - {payment.subscription.plan.name}',
                            'description': payment.description,
                        },
                        'unit_amount': int(payment.amount * 100),
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'payment_id': payment.id,
                    'user_id': payment.user.id,
                    'subscription_id': payment.subscription.id if payment.subscription else None,
                }
            )

            payment.stripe_session_id = session.id
            payment.status = 'processing'
            payment.save()

            return {
                'checkout_url': session.url,
                'session_id': session.id,
                'payment_id': payment.id,
            }

        except stripe.error.StripeError as e:
            logger.error(f'Error creating checkout session {e}')
            payment.mark_as_failed(str(e))
            return None

    @staticmethod
    def create_payment_intent(payment: Payment) -> Optional[str]:
        '''Створює Payment Intent в Stripe'''
        try:
            intent = stripe.PaymentIntent.create(
                amount = int(payment.amount * 100),
                currency = payment.currency.lower(),
                customer = payment.stripe_customer_id,
                metadata = {
                    'payment_id': payment.id,
                    'user_id': payment.user.id,
                    'subscription_id': payment.subscription.id if payment.subscription else None,
                }
            )

            payment.stripe_payment_intent_id = intent.id
            payment.save()

            return intent.client_secret
        except stripe.error.StripeError as e:
            logger.error(f'Error creating payment intent {e}')
            payment.mark_as_failed(str(e))
            return None

    @staticmethod
    def refund_payment(payment: Payment,amount : Optional[Decimal]=None , reason:str="") -> bool:
        '''Повертає платіж через Stripe'''
        try:
            if not payment.stripe_payment_intent_id:
                return False

            refund_data = {
                'payment_intent' : payment.stripe_payment_intent_id,
                'metadata' : {
                    'payment_id' : payment.id,
                    'reason' : reason,
                }
            }

            if amount:
                refund_data['amount'] = int(amount * 100)

            refund = stripe.Refund.create(**refund_data)

            return refund.status == 'succeeded'

        except stripe.error.StripeError as e:
            logger.error(f'Error refunding payment {e}')
            return False


    @staticmethod
    def retrieve_session(session_id: str) -> Optional[Dict]:
        '''Отримує інформацію про сессію'''
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            return {
                'status' : session.payment_status,
                'payment_intent' : session.payment_intent,
                'customer' : session.customer,
                'metadata' : session.metadata,
            }
        except stripe.error.StripeError as e:
            logger.error(f'Error retrieving session {e}')
            return None


class PaymentService:
    """Основний сервіс для роботи з платежами"""

    @staticmethod
    def create_subscription_payment(user, plan: SubscriptionPlan) -> Tuple[Payment, Subscription]:
        """Створює платіж для підписки"""
        # Создаєм підписку
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status='pending',
            start_date=timezone.now(),
            end_date=timezone.now()  # Буде обновлено після оплати
        )

        # Создаєм платіж
        payment = Payment.objects.create(
            user=user,
            subscription=subscription,
            amount=plan.price,
            currency='USD',
            description=f'Subscription to {plan.name}',
            payment_method='stripe'
        )

        # Записуєм в історію
        SubscriptionHistory.objects.create(
            subscription=subscription,
            action='created',
            description=f'Subscription created for plan {plan.name}'
        )

        return payment, subscription

    @staticmethod
    def process_successful_payment(payment: Payment) -> bool:
        """Оброблює платіж"""
        try:
            payment.mark_as_succeeded()

            # Активуєм підписку
            if payment.subscription:
                payment.subscription.activate()

                # Записуєм в історію
                SubscriptionHistory.objects.create(
                    subscription=payment.subscription,
                    action='activated',
                    description='Subscription activated after successful payment',
                    metadata={'payment_id': payment.id}
                )

            logger.info(f"Payment {payment.id} processed successfully")
            return True

        except Exception as e:
            logger.error(f"Error processing successful payment {payment.id}: {e}")
            return False

    @staticmethod
    def process_failed_payment(payment: Payment, reason: str = "") -> bool:
        try:
            payment.mark_as_failed(reason)

            # Відміняєм
            if payment.subscription:
                payment.subscription.cancel()

                # Записуєм в історію
                SubscriptionHistory.objects.create(
                    subscription=payment.subscription,
                    action='payment_failed',
                    description=f'Payment failed: {reason}',
                    metadata={'payment_id': payment.id}
                )

            logger.info(f"Payment {payment.id} marked as failed")
            return True

        except Exception as e:
            logger.error(f"Error processing failed payment {payment.id}: {e}")
            return False

    @staticmethod
    def cancel_subscription(subscription: Subscription) -> bool:
        """Відміняє підписку"""
        try:
            subscription.cancel()

            # Видаляєм закріпленний пост, якшо є
            if hasattr(subscription.user, 'pinned_post'):
                subscription.user.pinned_post.delete()

            # Записуєм в історію
            SubscriptionHistory.objects.create(
                subscription=subscription,
                action='cancelled',
                description='Subscription cancelled by user'
            )

            logger.info(f"Subscription {subscription.id} cancelled")
            return True

        except Exception as e:
            logger.error(f"Error cancelling subscription {subscription.id}: {e}")
            return False


from typing import Dict
import logging

logger = logging.getLogger(__name__)


class WebhookService:
    """Сервіс для обробки webhook-подій"""

    @staticmethod
    def process_stripe_webhook(event_data: Dict) -> bool:
        """Обробляє Stripe webhook"""
        try:
            event_id = event_data.get('id')
            event_type = event_data.get('type')

            # Перевіряємо, чи не обробляли ми вже цю подію раніше
            if Webhook.objects.filter(event_id=event_id).exists():
                return True

            # Створюємо запис про подію в базі даних
            webhook_event = Webhook.objects.create(
                provider='stripe',
                event_id=event_id,
                event_type=event_type,
                data=event_data
            )

            # Обробляємо різні типи подій залежно від їх призначення
            success = False

            if event_type == 'checkout.session.completed':
                success = WebhookService._handle_checkout_completed(event_data)
            elif event_type == 'payment_intent.succeeded':
                success = WebhookService._handle_payment_succeeded(event_data)
            elif event_type == 'payment_intent.payment_failed':
                success = WebhookService._handle_payment_failed(event_data)
            elif event_type == 'charge.dispute.created':
                success = WebhookService._handle_dispute_created(event_data)
            else:
                # Невідомий тип події — позначаємо як ігнорований
                webhook_event.status = 'ignored'
                webhook_event.save()
                return True

            # Оновлюємо статус обробки події
            if success:
                webhook_event.mark_as_processed()
            else:
                webhook_event.mark_as_failed("Обробка завершилася невдачею")

            return success

        except Exception as e:
            logger.error(f"Помилка при обробці Stripe webhook: {e}")
            return False

    @staticmethod
    def _handle_checkout_completed(event_data: Dict) -> bool:
        """Обробляє успішне завершення сесії checkout"""
        try:
            session = event_data['data']['object']
            metadata = session.get('metadata', {})
            payment_id = metadata.get('payment_id')

            if not payment_id:
                logger.warning("У метаданих сесії checkout відсутній payment_id")
                return False

            payment = Payment.objects.get(id=payment_id)
            return PaymentService.process_successful_payment(payment)

        except Payment.DoesNotExist:
            logger.error(f"Платіж не знайдено для сесії checkout")
            return False
        except Exception as e:
            logger.error(f"Помилка при обробці завершеного checkout: {e}")
            return False

    @staticmethod
    def _handle_payment_succeeded(event_data: Dict) -> bool:
        """Обробляє успішне підтвердження платежу (payment intent)"""
        try:
            payment_intent = event_data['data']['object']
            metadata = payment_intent.get('metadata', {})
            payment_id = metadata.get('payment_id')

            if not payment_id:
                logger.warning("У метаданих payment intent відсутній payment_id")
                return False

            payment = Payment.objects.get(id=payment_id)
            payment.stripe_payment_intent_id = payment_intent['id']
            payment.save()

            return PaymentService.process_successful_payment(payment)

        except Payment.DoesNotExist:
            logger.error(f"Платіж не знайдено для payment intent")
            return False
        except Exception as e:
            logger.error(f"Помилка при обробці успішного платежу: {e}")
            return False

    @staticmethod
    def _handle_payment_failed(event_data: Dict) -> bool:
        """Обробляє невдалу спробу платежу"""
        try:
            payment_intent = event_data['data']['object']
            metadata = payment_intent.get('metadata', {})
            payment_id = metadata.get('payment_id')

            if not payment_id:
                logger.warning("У метаданих payment intent відсутній payment_id")
                return False

            payment = Payment.objects.get(id=payment_id)

            last_error = payment_intent.get('last_payment_error', {})
            error_message = last_error.get('message', 'Платіж відхилено')

            return PaymentService.process_failed_payment(payment, error_message)

        except Payment.DoesNotExist:
            logger.error(f"Платіж не знайдено для невдалого payment intent")
            return False
        except Exception as e:
            logger.error(f"Помилка при обробці невдалого платежу: {e}")
            return False

    @staticmethod
    def _handle_dispute_created(event_data: Dict) -> bool:
        """Обробляє створення диспуту (оскарження платежу)"""
        try:
            dispute = event_data['data']['object']
            charge_id = dispute.get('charge')

            logger.info(f"Створено диспут для транзакції (charge) {charge_id}")
            return True

        except Exception as e:
            logger.error(f"Помилка при обробці створеного диспуту: {e}")
            return False