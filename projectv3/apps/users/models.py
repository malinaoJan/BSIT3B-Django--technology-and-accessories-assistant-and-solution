from django.conf import settings
from django.db import models


class PhoneProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='phone_profile',
    )
    phone_number = models.CharField(max_length=16, unique=True, null=True, blank=True)

    def __str__(self):
        return self.phone_number or self.user.get_username()
