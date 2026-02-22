import pytest
from django.urls import reverse
from apps.subscribe.models import PinnedPost

@pytest.mark.django_db
class TestSubscription:
    def test_get_plans(self, api_client, subscription_plan):
        url = reverse('subscription-plans')
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data['results']) == 1

    def test_subscription_status_no_sub(self, auth_client):
        url = reverse('subscription-status')
        response = auth_client.get(url)
        assert response.status_code == 200
        assert response.data['has_subscription'] == False

    # def test_subscription_status_active(self, auth_client, active_subscription):
    #     url = reverse('subscription-status')
    #     response = auth_client.get(url)
    #     assert response.data['is_active'] == True

    def test_cancel_subscription(self, auth_client, active_subscription):
        url = reverse('cancel-subscription')
        response = auth_client.post(url)
        assert response.status_code == 200
        active_subscription.refresh_from_db()
        assert active_subscription.status == 'cancelled'

@pytest.mark.django_db
class TestPinnedPost:
    def test_pin_post_with_subscription(self, auth_client, post, active_subscription):
        url = reverse('pin-post')
        response = auth_client.post(url, {'post_id': post.id})
        assert response.status_code == 201
        assert PinnedPost.objects.filter(post=post).exists()

    def test_pin_post_without_subscription(self, auth_client, post):
        url = reverse('pin-post')
        response = auth_client.post(url, {'post_id': post.id})
        assert response.status_code == 400

    def test_pin_other_user_post(self, api_client, post, user2, active_subscription):
        # user2 намагається закріпити пост user
        api_client.force_authenticate(user=user2)
        url = reverse('pin-post')
        response = api_client.post(url, {'post_id': post.id})
        assert response.status_code == 400

    def test_unpin_post(self, auth_client, user, post, active_subscription):
        PinnedPost.objects.create(user=user, post=post)
        url = reverse('unpin-post')
        response = auth_client.post(url)
        assert response.status_code == 200
        assert not PinnedPost.objects.filter(post=post).exists()