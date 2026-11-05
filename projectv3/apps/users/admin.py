from django.contrib import admin

from .models import PhoneProfile


@admin.register(PhoneProfile)
class PhoneProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number')
    search_fields = ('user__username', 'user__email', 'phone_number')
