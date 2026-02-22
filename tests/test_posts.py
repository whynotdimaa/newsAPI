import pytest
from django.urls import reverse
from apps.main.models import Post

@pytest.mark.django_db
class TestPostList:
    def test_list_published_posts_anonymous(self, api_client, post):
        url = reverse('post-list')
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data['count'] == 1

    def test_draft_hidden_from_anonymous(self, api_client, user, category):
        Post.objects.create(
            title='Draft',
            content='...',
            author=user,
            category=category,
            status='draft'
        )
        url = reverse('post-list')
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data['count'] == 0

    def test_author_sees_own_draft(self, auth_client, user, category):
        Post.objects.create(
            title='Draft',
            content='...',
            author=user,
            category=category,
            status='draft'
        )
        url = reverse('post-list')
        response = auth_client.get(url)
        assert response.data['count'] == 1

@pytest.mark.django_db
class TestPostCreate:
    def test_create_post_authenticated(self, auth_client, category):
        url = reverse('post-list')
        response = auth_client.post(url, {
            'title': 'New Post',
            'content': 'Content here',
            'category': category.id,
            'status': 'published'
        })
        assert response.status_code == 201

    def test_create_post_unauthenticated(self, api_client, category):
        url = reverse('post-list')
        response = api_client.post(url, {
            'title': 'New Post',
            'content': 'Content',
            'category': category.id,
        })
        assert response.status_code == 401

@pytest.mark.django_db
class TestPostDetail:
    def test_get_post(self, api_client, post):
        url = reverse('post-detail', kwargs={'slug': post.slug})
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data['title'] == 'Test Post'

    def test_views_increment(self, api_client, post):
        url = reverse('post-detail', kwargs={'slug': post.slug})
        api_client.get(url)
        post.refresh_from_db()
        assert post.views_count == 1

    def test_delete_own_post(self, auth_client, post):
        url = reverse('post-detail', kwargs={'slug': post.slug})
        response = auth_client.delete(url)
        assert response.status_code == 204

    def test_delete_other_user_post(self, api_client, post, user2):
        api_client.force_authenticate(user=user2)
        url = reverse('post-detail', kwargs={'slug': post.slug})
        response = api_client.delete(url)
        assert response.status_code == 403