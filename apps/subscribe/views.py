from django.db import transaction
from django.db.models.signals import post_save
from django.http import Http404
from rest_framework.decorators import api_view , permission_classes
from django.shortcuts import render
from rest_framework import generics, permissions, status, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.shortcuts import get_object_or_404
from datetime import timezone
from .models import Subscription, SubscriptionPlan, SubscriptionHistory, PinnedPost
from .serializers import (SubscriptionPlanSerializer, SubscriptionSerializer,
                          SubscriptionCreateSerializer, PinnedPostSerializer,
                          SubscriptionHistorySerializer, UserSubscriptionStatusSerializer,
                          PinPostSerializer, UnpinPostSerializer)
from apps.main.models import Post
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes


@extend_schema_view(
    get=extend_schema(
        summary="Список доступних планів підписки",
        description="Повертає перелік усіх активних тарифних планів, які користувачі можуть придбати.",
        tags=['Плани підписки']
    )
)

class SubscriptionPlanListView(generics.ListAPIView):
    queryset = SubscriptionPlan.objects.filter(is_active=True)
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [permissions.AllowAny]

@extend_schema_view(
    get=extend_schema(
        summary="Деталі плану підписки",
        description="Повертає детальну інформацію про конкретний тарифний план за його ID.",
        tags=['Плани підписки']
    )
)
class SubscriptionPlanDetailView(generics.RetrieveAPIView):
    queryset = SubscriptionPlan.objects.filter(is_active=True)
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [permissions.AllowAny]


@extend_schema_view(
    get=extend_schema(
        summary="Моя поточна підписка",
        description="Повертає інформацію про активну підписку поточного користувача, включаючи дату закінчення та статус.",
        tags=['Керування підпискою']
    )
)
class UserSubscriptionView(generics.RetrieveAPIView):
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        '''Вертає підписку користувача'''
        try:
            return self.request.user.subscription
        except Subscription.DoesNotExist:
            return None

    def retrieve(self, request, *args, **kwargs):
        '''Вертає інформацію про підписку'''
        subscription = self.get_object()
        if subscription:
            serializer = self.get_serializer(subscription)
            return Response(serializer.data)
        else:
            return Response({
                'detail' : 'No subscription found'
            }, status=status.HTTP_404_NOT_FOUND)


@extend_schema_view(
    get=extend_schema(
        summary="Історія підписки",
        description="Повертає повний список подій (оплата, активація, скасування) для поточного користувача.",
        tags=['Керування підпискою']
    )
)
class SubscriptionHistoryView(generics.ListAPIView):
    serializer_class = SubscriptionHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        '''Вертає історію підписки юзера'''
        try:
            subscription = self.request.user.subscription
            return subscription.history.all()
        except Subscription.DoesNotExist:
            return SubscriptionHistory.objects.none()


@extend_schema_view(
    get=extend_schema(summary="Мій закріплений пост", tags=['Закріплені пости']),
    put=extend_schema(summary="Оновити закріплений пост", tags=['Закріплені пости']),
    patch=extend_schema(summary="Частково оновити закріплений пост", tags=['Закріплені пости']),
    delete=extend_schema(summary="Видалити закріплений пост", tags=['Закріплені пости'])
)
class PinnedPostView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PinnedPostSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        '''Повертає закріпленний пост'''
        try:
            return self.request.user.pinned_post
        except PinnedPost.DoesNotExist:
            return None
    def retrieve(self, request, *args, **kwargs):
        '''Повертає інформацію про закріпленний пост'''
        pinned_post = self.get_object()
        if pinned_post:
            serializer = self.get_serializer(pinned_post)
            return Response(serializer.data)
        else:
            return Response({
                'detail' : 'No pinned post found'
            },status=status.HTTP_404_NOT_FOUND)
    def update(self, request, *args, **kwargs):
        '''Обновляє закріпленний пост'''
        if not hasattr(request.user, 'subscription') or not request.user.subscription.is_active:
            return Response({
                'error' : 'Active subscription not found'
            },status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)
    def destroy(self, request, *args, **kwargs):
        '''Видаляє закріпленний пост'''
        pinned_post = self.get_object()
        if pinned_post:
            pinned_post.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response({
                'detail' : 'No pinned post found'
            },status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    tags=['Керування підпискою'],
    summary="Статус підписки",
    description="Повертає інформацію про те, чи активна підписка у користувача та чи може він закріплювати пости."
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def subscription_status(request):
    '''Вертає статус підписки'''
    serializer = UserSubscriptionStatusSerializer(request.user)
    return Response(serializer.data)


@extend_schema(
    tags=['Закріплені пости'],
    summary="Закріпити пост",
    description="Дозволяє автору з активною підпискою закріпити один свій пост у стрічці.",
    request=PinPostSerializer,
    responses={201: PinnedPostSerializer}
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def pin_post(request):
    '''Закріпляє пост'''
    serializer = PinPostSerializer(data=request.data, context={'request': request})

    if serializer.is_valid():
        post_id = serializer.validated_data['post_id']

        try:
            with transaction.atomic():
                post = get_object_or_404(Post, id = post_id, status = 'published')

                #Провіряєм права
                if post.author != request.user:
                    return Response({
                        'error' : 'You can only pin your own post'
                    },status=status.HTTP_403_FORBIDDEN)
                #Провіряєм підписку
                if not hasattr(request.user, 'subscription') or not request.user.subscription.is_active:
                    return Response({
                        'error' : 'Active subscription not found'
                    },status=status.HTTP_403_FORBIDDEN)
                # удаляєм закріпленний пост
                if hasattr(request.user, 'pinned_post'):
                    request.user.pinned_post.delete()
                pinned_post = PinnedPost.objects.create(
                    user = request.user,
                    post = post,
                )

                response_serializer = PinnedPostSerializer(pinned_post)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'error' : str(e)
            },status=status.HTTP_400_BAD_REQUEST)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=['Закріплені пости'],
    summary="Відкріпити пост",
    description="Видаляє поточний закріплений пост користувача.",
    request=UnpinPostSerializer
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def unpin_post(request):
    '''анпін поста'''
    serializer = UnpinPostSerializer(data=request.data, context={'request': request})

    if serializer.is_valid():
        try:
            pinned_post = request.user.pinned_post
            pinned_post.delete()

            return Response({
                'message' : 'Pinned post deleted'
            },status=status.HTTP_200_OK)
        except PinnedPost.DoesNotExist:
            return Response({
                'error' : 'No pinned post found'
            },status=status.HTTP_404_NOT_FOUND)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=['Керування підпискою'],
    summary="Скасувати підписку",
    description="Відключає активну підписку користувача та автоматично видаляє його закріплений пост.",
    responses={200: OpenApiTypes.OBJECT}
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def cancel_subscription(request):
    '''Відміняєм підписку юзера'''
    try:
        subscription = request.user.subscription


        if not subscription.is_active:
            return Response({
                'error' : 'Active subscription not found'
            },status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            subscription.cancel()

            if hasattr(request.user, 'pinned_post'):
                request.user.pinned_post.delete()

            SubscriptionHistory.objects.create(
                subscription = subscription,
                action = 'canceled',
                description = 'Subcription canceled'
            )
        return Response({
            'message' : 'Subcription canceled'
        },status=status.HTTP_200_OK)
    except Subscription.DoesNotExist:
        return Response({
            'error' : 'No subscription found'
        },status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    tags=['Закріплені пости'],
    summary="Список усіх закріплених постів",
    description="Публічний метод, що повертає всі закріплені пости на сайті з даними про авторів та категорії."
)
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def pinned_post_list(request):
    '''Повертає список всіх закріпленних постів'''
    pinned_posts = (PinnedPost.objects.select_related
            ('post', 'post__author', 'post__category', 'user__subscription'
    ).filter(
        user__subscription__status = 'active',
        user__subscription__end_date__gt = timezone.now(),
        post__status ='published'
    ).order_by('pinned_at'))

    # Формуєм відповідь з інфою про пост
    posts_data = []
    for pinned_posts in pinned_posts:
        post = pinned_post.post
        posts_data.append({
            'id' : post.id,
            'title' : post.title,
            'slug' : post.slug,
            'content' : post.content[:200] + '...' if len(post.content) > 200 else post.content,
            'image' : post.image.url if post.image else None,
            'category' : post.category.name if post.category else None,
            'author' : {
               'id' : post.author.id,
               'username' : post.author.username,
               'full_name' : post.author.full_name,
        },
            'views_count' : post.views_count,
            'comments_count' : post.comments_count,
            'created_at' : post.created_at,
            'pinned_at' : pinned_posts.pinned_at,
            'is_pinned' : True,
        })
    return Response({
        'count' : len(posts_data),
        'results' : posts_data,
    })


@extend_schema(
    tags=['Закріплені пости'],
    summary="Чи можна закріпити цей пост",
    description="Перевіряє, чи має пост статус опублікованого, чи є користувач автором та чи є в нього активна підписка.",
    parameters=[OpenApiParameter(name="post_id", type=int, location=OpenApiParameter.PATH)]
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def can_pin_post(request, post_id):
    '''Провіряє чи можна закріпити'''
    try:
        post = get_object_or_404(Post, id=post_id, status = 'published')

        checks = {
            'post_exists' : True,
            'is_own_post' : post.author == request.user,
            'has_subscription' : hasattr(request.user, 'subscription'),
            'subscription_active' : False,
            'can_pin' : False,
        }

        if checks['has_subscription']:
            checks['subscription_active'] = request.user.subscription.is_active

        checks['can_pin'] = (
            checks['is_own_post'] and
            checks['has_subscription'] and
            checks['subscription_active']
        )

        return Response({
            'post_id' : post_id,
            'can_pin' : checks['can_pin'],
            'checks' : checks,
            'message' : 'Can pin post' if checks['can_pin'] else 'Can not pin post'
        })
    except Post.DoesNotExist:
        return Response({
            'post_id' : post_id,
            'can_pin' : False,
            'checks' : {'post_exists' : False},
            'message' : 'Post does not exist'
        },status=status.HTTP_404_NOT_FOUND)