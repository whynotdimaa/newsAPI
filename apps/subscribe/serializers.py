from rest_framework import serializers
from django.utils import timezone
from .models import SubscriptionPlan, Subscription, PinnedPost, SubscriptionHistory

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ['id', 'name', 'price', 'duration_days',
                  'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']

    def to_representation(self, instance):
        '''Переоприділяєм для гарантії коректного виводу'''
        data = super().to_representation(instance)

        # Впевнетись що features це об'єкт
        if not data.get('features'):
            data['features'] = []

        return data

class SubscriptionSerializer(serializers.ModelSerializer):
    plan_info = SubscriptionPlanSerializer(read_only=True, source='plan')
    user_info = serializers.SerializerMethodField()
    is_active = serializers.ReadOnlyField()
    days_remaining = serializers.ReadOnlyField()

    class Meta:
        model = Subscription
        fields =[
            'id', 'user', 'user_info', 'plan', 'plan_info','status', 'start_date','end_date','auto_renew', 'is_active', 'days_remaining', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id','user', 'status', 'start_date', 'end_date' ,'created_at', 'updated_at']

    def get_user_info(self, obj):
        """Інфо про користувача"""
        return {
            'id' : obj.user.id,
            'username' : obj.user.username,
            'full_name' : obj.user.full_name,
            'email' : obj.user.email,
        }

class SubscriptionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields =['plan']

    def validate_plan(self, value):
        '''Валідація тарифного плану'''
        if not value.is_active:
            raise serializers.ValidationError('Selected plan is not active')
        return value

    def validate(self, attrs):
        '''Обща валідація'''
        user = self.context['request'].user

        #Провіряєм чи є активна підписка
        if hasattr(user, 'subscription') and user.subscription.is_active():
            raise serializers.ValidationError({'non_field_errors' : ['User has already active subscription']})
        return attrs

    def create(self, validated_data):
        '''Створює підписку'''
        validated_data['user'] = self.context['request'].user
        validated_data['status'] = 'pending'
        validated_data['start_date'] = timezone.now()
        validated_data['end_date'] = timezone.now()

        return super().create(validated_data)

class PinnedPostSerializer(serializers.ModelSerializer):
    post_info = serializers.SerializerMethodField()
    class Meta:
        model = PinnedPost
        fields =['id', 'post', 'post_info', 'pinned_at']
        read_only_fields = ['id','pinned_at']
    def get_post_info(self, obj):
        '''Повертає інформацію про пост'''
        return {
            'id' : obj.post.id,
            'title' : obj.post.title,
            'slug' : obj.post.slug,
            'content' : obj.post.content,
            'image' : obj.post.image if obj.post.image else None,
            'views' : obj.post.views_count,
            'created_at' : obj.post.created_at,
        }
    def validate_post(self,value):
        '''Валідація поста для закріплення'''
        user = self.context['request'].user

        # Провіряєм що пост юзера
        if value.author != user:
            raise serializers.ValidationError('You can pin only your posts')

        # Провіряєм що пост опублікований
        if value.status != 'published':
            raise serializers.ValidationError('Status is not published')

        return value

    def validate(self, attrs):
        '''Обща валідація'''
        user = self.context['request'].user

        # Провіряєм чи є активна підписка
        if not hasattr(user, 'subscription') or not user.subscription.is_active():
            raise serializers.ValidationError({'non_field_errors' : ['Active subscription is required to pin']})

        return attrs

    def create(self, validated_data):
        '''Створює закріпленний пост'''
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class SubscriptionHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionHistory
        fields = ['id', 'action', 'description', 'metadata', 'created_at']
        read_only_fields = ['id', 'created_at']


class UserSubscriptionStatusSerializer(serializers.ModelSerializer):
    has_subscription = serializers.BooleanField()
    is_active = serializers.BooleanField()
    subscription = SubscriptionSerializer(allow_null=True)
    pinned_post = PinnedPostSerializer(allow_null=True)
    can_pin_posts = serializers.BooleanField()

    def to_representation(self, instance):
        '''Формує відповідь з інформацією про підписку'''
        user = instance
        has_subscription = hasattr(user, 'subcription')
        subscription = user.subscription if has_subscription else None
        is_active = subscription.is_active if subscription else False
        pinned_post = getattr(user, 'pinned_post', None) if is_active else None

        return {
            'has_subscription' : has_subscription,
            'is_active' : is_active,
            'subscription' : SubscriptionSerializer(subscription).data if subscription else None,
            'pinned_post' : PinnedPostSerializer(pinned_post).data if pinned_post else None,
            'can_pin_post' : is_active,
        }

class PinPostSerializer(serializers.Serializer):
    post_id = serializers.IntegerField()

    def validate_post_id(self, value):
        '''Валідація ід поста'''
        from apps.main.models import Post

        try:
            post = Post.objects.get(id = value , status = 'published')
        except Post.DoesNotExist:
            raise serializers.ValidationError('Post does not exist')

        user = self.context['request'].user
        if post.author != user:
            raise serializers.ValidationError('You can pin only your posts')
        return value
    def validate(self, attrs):
        '''Обща валідація'''
        user = self.context['request'].user
        if not hasattr(user, 'subscription') or not user.subscription.is_active:
            raise serializers.ValidationError({'non_field_errors' : ['Active subscription is required to pin']})
        return attrs

class UnpinPostSerializer(serializers.Serializer):
    def validate(self, attrs):
        user = self.context['request'].user

        if not hasattr(user, 'pinned_post'):
           raise serializers.ValidationError('You are not pinned')
        return attrs

