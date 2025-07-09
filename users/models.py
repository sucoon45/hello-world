from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", _("Admin")
        FRONT_DESK = "FRONT_DESK", _("Front Desk")
        HOUSEKEEPING = "HOUSEKEEPING", _("Housekeeping")
        ACCOUNTING = "ACCOUNTING", _("Accounting")
        GUEST = "GUEST", _("Guest")

    role = models.CharField(
        max_length=50,
        choices=Role.choices,
        default=Role.GUEST,
    )
    # Add any other custom fields for your user model here
    # For example: phone_number = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return self.username
