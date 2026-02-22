import pytest
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.main.models import Category, Post
from apps.subscribe.models import SubscriptionPlan, Subscription
from django.utils import timezone
from datetime import timedelta

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='testuser',
        email='test@test.com',
        password='testpass123'
    )

@pytest.fixture
def user2(db):
    return User.objects.create_user(
        username='testuser2',
        email='test2@test.com',
        password='testpass123'
    )

@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client

@pytest.fixture
def category(db):
    return Category.objects.create(
        name='Test Category',
        description='Test description'
    )

@pytest.fixture
def post(db, user, category):
    return Post.objects.create(
        title='Test Post',
        content='Test content',
        author=user,
        category=category,
        status='published'
    )

@pytest.fixture
def subscription_plan(db):
    return SubscriptionPlan.objects.create(
        name='Premium',
        price=12.00,
        duration_days=30,
        stripe_price_id='price_test_123',
        features='pin_posts',
        is_active=True
    )

@pytest.fixture
def active_subscription(user, subscription_plan):
    from django.utils import timezone
    from datetime import timedelta
    return Subscription.objects.create(
        user=user,
        plan=subscription_plan,
        status='active',
        start_date=timezone.now(),
        end_date=timezone.now() + timedelta(days=30)
    )

