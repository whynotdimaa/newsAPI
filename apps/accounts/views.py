from django.shortcuts import render
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import login

from . models import User
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
)
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

@extend_schema(
    tags=['Користувачі'],
    summary="Реєстрація нового користувача",
    description="Створює новий обліковий запис. Після успішної реєстрації користувач може увійти через ендпоінт входу."
)
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)

        return Response({
            'user' : UserProfileSerializer(user).data,
            'refresh' : str(refresh),
            'access' : str(refresh.access_token),
            'message' : 'User registered successfully!'
        }, status=status.HTTP_201_CREATED)

@extend_schema(
    tags=['Аутентифікація'],
    summary="Вхід у систему",
    description="Приймає email та пароль, повертає дані користувача та токени доступу."
)
class LoginView(generics.GenericAPIView):
    serializer_class = UserLoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        login(request, user)
        refresh = RefreshToken.for_user(user)

        return Response({
            'user': UserProfileSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'message': 'User login successfully!'
        }, status=status.HTTP_200_OK)

@extend_schema_view(
    get=extend_schema(
        summary="Отримання профілю користувача",
        description="Повертає детальні дані поточного авторизованого користувача.",
        tags=['Користувачі']
    ),
    put=extend_schema(
        summary="Повне оновлення профілю",
        description="Дозволяє змінити всі дані профілю (ім'я, біографія, аватар тощо).",
        tags=['Користувачі']
    ),
    patch=extend_schema(
        summary="Часткове оновлення профілю",
        description="Дозволяє змінити окремі поля профілю користувача.",
        tags=['Користувачі']
    )
)
class ProfileView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method == 'PUT' or self.request.method == 'PATCH':
            return UserUpdateSerializer
        return UserProfileSerializer

@extend_schema(
    tags=['Користувач'],
    summary="Зміна паролю",
    description="Дозволяє авторизованому користувачу змінити свій пароль, підтвердивши старий."
)
class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            'message': 'Password updated successfully!'
        }, status=status.HTTP_200_OK)

@extend_schema(
    tags=['Аутентифікація'],
    summary="Вихід із системи",
    description="Додає refresh токен у чорний список, роблячи його недійсним."
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout(request):
    try:
        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({
            'message': 'User logged out successfully!'
        },status=status.HTTP_200_OK)
    except Exception:
        return Response({
            'message': 'Invalid token'
        },status=status.HTTP_400_BAD_REQUEST)