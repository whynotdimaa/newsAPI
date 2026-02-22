import pytest
from django.urls import reverse
from apps.comments.models import Comment

@pytest.mark.django_db
class TestComments:
    def test_create_comment(self, auth_client, post):
        url = reverse('comment-list')
        response = auth_client.post(url, {
            'post': post.id,
            'content': 'Test comment'
        })
        assert response.status_code == 201

    def test_create_comment_unauthenticated(self, api_client, post):
        url = reverse('comment-list')
        response = api_client.post(url, {
            'post': post.id,
            'content': 'Test comment'
        })
        assert response.status_code == 401

    def test_create_reply(self, auth_client, post, user):
        comment = Comment.objects.create(
            post=post, author=user, content='Parent'
        )
        url = reverse('comment-list')
        response = auth_client.post(url, {
            'post': post.id,
            'parent': comment.id,
            'content': 'Reply'
        })
        assert response.status_code == 201

    def test_soft_delete_comment(self, auth_client, post, user):
        comment = Comment.objects.create(
            post=post, author=user, content='To delete'
        )
        url = reverse('comment-detail', kwargs={'pk': comment.id})
        auth_client.delete(url)
        comment.refresh_from_db()
        assert comment.is_active == False

    # def test_get_post_comments(self, api_client, post, user):
    #     Comment.objects.create(post=post, author=user, content='Comment 1')
    #     Comment.objects.create(post=post, author=user, content='Comment 2')
    #     url = reverse('post-comments', kwargs={'post_id': post.id})
    #     response = api_client.get(url)
    #     assert response.status_code == 200
    #     assert len(response.data['comments']) == 2