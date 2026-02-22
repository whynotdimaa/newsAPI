from rest_framework.decorators import api_view , permission_classes
from django.shortcuts import render
from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import Comment
from .serializers import (CommentSerializer, CommentCreateSerializer, CommentDetailSerializer, CommentUpdateSerializer)
from .permissions import IsAuthorOrReadOnly
from apps.main.models import Post
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

@extend_schema_view(
    get=extend_schema(
        summary="Список усіх активних коментарів",
        description="Повертає перелік усіх коментарів, які мають статус `is_active=True`. Підтримує фільтрацію за постом, автором та батьківським коментарем.",
        tags=['Коментарі']
    ),
    post=extend_schema(
        summary="Створити новий коментар",
        description="Дозволяє авторизованому користувачу залишити коментар до опублікованого поста або відповісти на інший коментар.",
        tags=['Коментарі']
    )
)
class CommentListCreate(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['post', 'author', 'parent']
    search_fields = ['content']
    ordering_fields = ['created_at','updated_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return Comment.objects.filter(is_active=True).select_related('author','post','parent')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CommentCreateSerializer
        return CommentSerializer

@extend_schema_view(
    get=extend_schema(summary="Деталі коментаря", tags=['Коментарі']),
    put=extend_schema(summary="Повне оновлення коментаря", tags=['Коментарі']),
    patch=extend_schema(summary="Часткове оновлення коментаря", tags=['Коментарі']),
    delete=extend_schema(
        summary="Видалити коментар (Soft Delete)",
        description="Замість повного видалення з бази, встановлює прапор `is_active=False`.",
        tags=['Коментарі']
    )
)
class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Comment.objects.filter(is_active=True).select_related('author','post')
    serializer_class = CommentDetailSerializer
    permission_classes = [IsAuthorOrReadOnly]

    def get_serializer_class(self):
        if self.request.method in ['PUT','PATCH']:
            return CommentUpdateSerializer
        return CommentDetailSerializer

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()
@extend_schema(
    tags=['Коментарі'],
    summary="Мої коментарі",
    description="Повертає список усіх коментарів, залишених поточним авторизованим користувачем."
)
class MyCommentsView(generics.ListAPIView):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['post', 'parent', 'is_active']
    search_fields = ['content']
    ordering_fields = ['created_at','updated_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return Comment.objects.filter(author = self.request.user).select_related(
            'post','parent'
        )
@extend_schema(
    tags=['Коментарі'],
    summary="Коментарі до конкретного поста",
    description="Повертає деревоподібну структуру коментарів (головні коментарі та відповіді) для вказаного поста.",
    parameters=[
        OpenApiParameter(name="post_id", type=int, location=OpenApiParameter.PATH, description="ID поста")
    ]
)
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def post_comments(request, post_id):

    post = get_object_or_404(Post, id = post_id, status = 'published')

    comments = Comment.objects.filter(
        post = post,
        parent = None,
        is_active = True
    ).select_related('author').prefetch_related(
        'replies__author'
    ).order_by('-created_at')
    serializer = CommentDetailSerializer(comments, many = True, context = {'request': request})
    return Response({
        'post': {
            'id': post_id,
            'title': post.title,
            'slug': post.slug,
        },
        'comments': serializer.data,
        'comments_count': post.comment.filter(is_active = True).count(),

    })

@extend_schema(
    tags=['Коментарі'],
    summary="Список відповідей на коментар",
    description="Повертає всі дочірні коментарі (відповіді) для конкретного батьківського коментаря.",
    parameters=[
        OpenApiParameter(name="comment_id", type=int, location=OpenApiParameter.PATH, description="ID батьківського коментаря")
    ]
)
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def comment_replies(request, comment_id):
    parent_comment = get_object_or_404(Comment, id = comment_id, is_active = True)
    replies = Comment.objects.filter(
        parent = parent_comment,
        is_active = True
    ).select_related('author').order_by('-created_at')

    serializer = CommentSerializer(replies, many = True, context = {'request': request})

    return Response({
        'parent_comment': CommentSerializer(parent_comment, context = {'request': request}).data,
        'replies': serializer.data,
        'replies_count': replies.count(),
    })