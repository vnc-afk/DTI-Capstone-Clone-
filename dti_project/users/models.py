from datetime import timedelta
import secrets
from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.urls import reverse
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField

# Create your models here.

class User(AbstractUser):
    class Roles(models.TextChoices):
        BUSINESS_OWNER = "business_owner", "Business Owner"
        ADMIN = "admin", "Admin"
        COLLECTION_AGENT = "collection_agent", "Collection Agent"

    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        default='profile_pictures/default-avatar-icon.jpg',
        blank=True
    )
    role = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.BUSINESS_OWNER
    )
    is_verified = models.BooleanField(default=False)
    verification_code = models.CharField(max_length=6, blank=True, null=True)
    verification_code_expiration_date = models.DateTimeField(blank=True, null=True)

    default_address = EncryptedCharField(max_length=255, blank=True, null=True)
    default_phone = EncryptedCharField(max_length=11, blank=True, null=True)
    birthday = EncryptedCharField(blank=True, null=True)

    dti_office = EncryptedCharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Only applicable if the user is a collection agent."
    )
    
    official_designation = EncryptedCharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Only applicable if the user is a collection agent."
    )
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def get_absolute_url(self):
        return reverse("profile", args=[self.pk])
    
    def generate_secure_otp_code(self):
        """Generate cryptographically secure 6-digit OTP and save to user"""
        code = ''.join(secrets.choice('0123456789') for _ in range(6))
        self.verification_code = code
        self.verification_code_expiration_date = timezone.now() + timedelta(minutes=30)  # expires in 30 minutes
        self.save(update_fields=["verification_code", "verification_code_expiration_date"])
        return code
    
    def is_verification_code_valid(self, code):
        """Check if verification code is valid and not expired"""
        return (
            self.verification_code == code and
            self.verification_code_expiration_date and
            timezone.now() < self.verification_code_expiration_date  # Fixed: now() and < instead of >
        )

    def get_full_name(self):
        parts = [self.first_name]
        if getattr(self, 'middle_name', None):  # safe check
            parts.append(self.middle_name)
        parts.append(self.last_name)
        return " ".join(filter(None, parts))
    
    def new_notifications(self):
        return self.notifications.filter(is_read=False)
    
    def save(self, *args, **kwargs):
        """
        Automatically fill DTI office and official designation
        if the user is a collection agent.
        """
        if self.role == self.Roles.COLLECTION_AGENT:
            # Apply defaults only if empty
            if not self.dti_office:
                self.dti_office = "DTI Albay Provincial Office"
            if not self.official_designation:
                self.official_designation = "Special Collecting Officer"
        else:
            # Wipe these fields for non-collection agents
            self.dti_office = None
            self.official_designation = None

        # Force superusers to always be admin
        if self.is_superuser:
            self.role = self.Roles.ADMIN
            
        super().save(*args, **kwargs)
