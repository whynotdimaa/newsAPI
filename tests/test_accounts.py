import pytest
from django.urls import reverse

@pytest.mark.django_db
class TestRegistration:
    def test_register_success(self, api_client):
        url = reverse('register')
        data = {
            'username': 'newuser',
            'email': 'new@test.com',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!',
        }
        response = api_client.post(url, data)
        assert response.status_code == 201
        assert 'access' in response.data
        assert 'refresh' in response.data

    def test_register_passwords_not_match(self, api_client):
        url = reverse('register')
        data = {
            'username': 'newuser',
            'email': 'new@test.com',
            'password': 'StrongPass123!',
            'password_confirm': 'WrongPass123!',
        }
        response = api_client.post(url, data)
        assert response.status_code == 400

    def test_register_duplicate_email(self, api_client, user):
        url = reverse('register')
        data = {
            'username': 'anotheruser',
            'email': 'test@test.com',  # вже існує
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!',
        }
        response = api_client.post(url, data)
        assert response.status_code == 400

@pytest.mark.django_db
class TestLogin:
    def test_login_success(self, api_client, user):
        url = reverse('login')
        response = api_client.post(url, {
            'email': 'test@test.com',
            'password': 'testpass123'
        })
        assert response.status_code == 200
        assert 'access' in response.data

    def test_login_wrong_password(self, api_client, user):
        url = reverse('login')
        response = api_client.post(url, {
            'email': 'test@test.com',
            'password': 'wrongpass'
        })
        assert response.status_code == 400

@pytest.mark.django_db
class TestProfile:
    def test_get_profile_authenticated(self, auth_client):
        url = reverse('profile')
        response = auth_client.get(url)
        assert response.status_code == 200
        assert response.data['email'] == 'test@test.com'

    def test_get_profile_unauthenticated(self, api_client):
        url = reverse('profile')
        response = api_client.get(url)
        assert response.status_code == 401

@pytest.mark.django_db
class TestChangePassword:
    def test_change_password_success(self, auth_client):
        url = reverse('change_password')
        response = auth_client.put(url, {
            'old_password': 'testpass123',
            'new_password': 'NewStrongPass123!',
            'new_password_confirm': 'NewStrongPass123!'
        })
        assert response.status_code == 200

    def test_change_password_wrong_old(self, auth_client):
        url = reverse('change_password')
        response = auth_client.put(url, {
            'old_password': 'wrongpass',
            'new_password': 'NewStrongPass123!',
            'new_password_confirm': 'NewStrongPass123!'
        })
        assert response.status_code == 400