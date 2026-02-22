from django.db.models.signals import post_save ,pre_delete
from django.dispatch import receiver
from django.utils import timezone
from . models import Subscription, PinnedPost, SubscriptionHistory

@receiver(post_save,sender=Subscription)
def create_subscription_history(sender, instance, created, **kwargs):
    '''Обробник збереження підписки'''
    if created:
        # Створюєм запис в історії при створенні підписки
        SubscriptionHistory.objects.create(
            subscription=instance,
            action = 'created',
            description = f'Subscription created for plan {instance.plan.name}',
        )
    else:
        # Провіряєм чи помінявся статус
        if hasattr(instance, '_previous_status'):
            if instance._previous_status != instance.status:
                SubscriptionHistory.objects.create(
                    subscription=instance,
                    action = instance.status,
                    description = f'Subscription status updated for plan {instance.plan.name} to {instance.status}',
                )

@receiver(pre_delete,sender=Subscription)
def subscription_delete(sender, instance, **kwargs):
    '''Обробник видалення підписки'''
    # Удаляєм закріпленний пост
    try:
        instance.user.pinned_posts.delete()
    except PinnedPost.DoesNotExist:
        pass

@receiver(post_save,sender=PinnedPost)
def pinned_post_post_save(sender, instance, created, **kwargs):
    '''Обробник збереженя закріпленого поста'''
    if created:
        #Провіряєм шо в юзера є активна підписка
        if not hasattr(instance.user, 'subscription') or not instance.user.subscription.is_active:
            instance.delete()
            return

        # Записуєм в історію підписки
        SubscriptionHistory.objects.create(
            subscription=instance.user.subscription,
            action = 'post_pinned',
            description = f'Post "{instance.post.title}" pinned',
            metadata = {
                'post_id': instance.post.id,
                'post_title': instance.post.title,
            }
        )

@receiver(pre_delete,sender=PinnedPost)
def pinned_post_pre_delete(sender, instance, **kwargs):
    '''Обробник видалення закріпленого поста'''
    if hasattr(instance.user, 'subscription'):
        SubscriptionHistory.objects.create(
            subscription=instance.user.subscription,
            action = 'post_unpinned',
            description = f'Post "{instance.post.title}" unpinned',
            metadata = {
                'post_id': instance.post.id,
                'post_title': instance.post.title,
            }
        )