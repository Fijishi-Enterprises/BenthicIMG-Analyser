from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin


User = get_user_model()

# Unregister the default User admin class.
admin.site.unregister(User)

# Register our own User admin class, which extends the default class to
# display more fields and change the order.
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = [
        'username', 'is_active', 'is_staff', 'date_joined',
        'first_name', 'last_name', 'email']
