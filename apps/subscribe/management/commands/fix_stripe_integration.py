import stripe
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.subscribe.models import SubscriptionPlan

stripe.api_key = settings.STRIPE_SECRET_KEY


class Command(BaseCommand):
    help = 'Виправляє інтеграцію зі Stripe, створюючи реальні продукти та ціни'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Примусово перестворити, навіть якщо stripe_price_id вже існує',
        )

    def handle(self, *args, **options):
        force = options['force']

        # Перевіряємо підключення до Stripe
        try:
            stripe.Balance.retrieve()
            self.stdout.write(self.style.SUCCESS('✅ Підключення до Stripe працює'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Помилка підключення до Stripe: {e}'))
            return

        # Обробляємо всі активні плани
        plans = SubscriptionPlan.objects.filter(is_active=True)

        for plan in plans:
            self.stdout.write(f'Обробляємо план: {plan.name}')

            # Перевіряємо, чи потрібно створювати новий Price ID
            if plan.stripe_price_id and not force and plan.stripe_price_id.startswith('price_'):
                self.stdout.write(f'  ⏭️ План уже має реальний Stripe ID: {plan.stripe_price_id}')
                continue

            try:
                # Створюємо або оновлюємо продукт у Stripe
                product = stripe.Product.create(
                    name=plan.name,
                    description=f"Subscription plan: {plan.name}",
                    metadata={
                        'plan_id': plan.id,
                        'django_model': 'SubscriptionPlan',
                        'created_by': 'django_management_command'
                    }
                )
                self.stdout.write(f'  ✅ Продукт створено: {product.id}')

                # Створюємо ціну для продукту
                price = stripe.Price.create(
                    product=product.id,
                    unit_amount=int(plan.price * 100),  # У центах
                    currency='usd',
                    recurring={'interval': 'month'},
                    metadata={
                        'plan_id': plan.id,
                        'django_model': 'SubscriptionPlan'
                    }
                )
                self.stdout.write(f'  ✅ Ціну створено: {price.id}')

                # Оновлюємо план у базі даних Django
                old_id = plan.stripe_price_id
                plan.stripe_price_id = price.id
                plan.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✅ План оновлено: {old_id} → {price.id}'
                    )
                )

            except stripe.error.StripeError as e:
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Помилка Stripe для плану {plan.name}: {e}')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Загальна помилка для плану {plan.name}: {e}')
                )

        self.stdout.write(
            self.style.SUCCESS('🎉 Обробка завершена! Перевірте Stripe Dashboard.')
        )