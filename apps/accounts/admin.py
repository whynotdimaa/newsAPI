from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email','username', 'first_name', 'last_name')
    list_filter = ('is_active','is_staff','is_superuser','created_at')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('-created_at',)

    fieldsets = (
    (None, {'fields': ('email', 'username', 'password')}),
    ('Personal info', {'fields': ('first_name', 'last_name', 'avatar', 'bio')}),
    ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups')}),
    ('Important dates', {'fields': ('last_login', 'date_joined','created_at')}),
    )

    add_fieldsets = (
    (None, {'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2'),
            }),
    )