
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


# 1. Product categories
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


# 2. Technology products and accessories
class Product(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )
    name = models.CharField(max_length=160)
    brand = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    specifications = models.JSONField(default=dict, blank=True)
    price = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.brand} {self.name}"


# 3. Devices owned or used by customers
class Device(models.Model):
    DEVICE_TYPES = [
        ("phone", "Phone"),
        ("tablet", "Tablet"),
        ("laptop", "Laptop"),
        ("desktop", "Desktop"),
        ("other", "Other"),
    ]

    brand = models.CharField(max_length=100)
    model_name = models.CharField(max_length=160)
    device_type = models.CharField(
        max_length=20, choices=DEVICE_TYPES, default="phone"
    )
    connector_type = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["brand", "model_name"],
                name="unique_device_model"
            )
        ]

    def __str__(self):
        return f"{self.brand} {self.model_name}"


# 4. Which products work with which devices
class Compatibility(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name="compatibilities"
    )
    device = models.ForeignKey(
        Device, on_delete=models.CASCADE,
        related_name="compatibilities"
    )
    compatibility_notes = models.CharField(max_length=255, blank=True)
    verified = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "device"],
                name="unique_product_device_compatibility"
            )
        ]

    def __str__(self):
        return f"{self.product} - {self.device}"


# 5. Additional customer profile information
class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    phone = models.CharField(max_length=30, blank=True)
    preferred_budget = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True
    )
    preferred_device = models.ForeignKey(
        Device, on_delete=models.SET_NULL,
        null=True, blank=True
    )

    def __str__(self):
        return self.user.username


# 6. A customer's product recommendation request
class RecommendationRequest(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    device = models.ForeignKey(
        Device, on_delete=models.SET_NULL,
        null=True, blank=True
    )
    intended_use = models.CharField(max_length=160)
    budget_min = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(0)]
    )
    budget_max = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Request #{self.pk}: {self.intended_use}"


# 7. Products recommended for each request
class Recommendation(models.Model):
    request = models.ForeignKey(
        RecommendationRequest,
        on_delete=models.CASCADE,
        related_name="recommendations"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name="recommendations"
    )
    reason = models.CharField(max_length=255, blank=True)
    rank = models.PositiveSmallIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["request", "product"],
                name="unique_recommended_product_per_request"
            )
        ]

    def __str__(self):
        return f"{self.product} for request #{self.request_id}"


# 8. Troubleshooting articles and solutions
class TroubleshootingGuide(models.Model):
    title = models.CharField(max_length=180)
    device_type = models.CharField(max_length=60, blank=True)
    issue = models.CharField(max_length=180)
    symptoms = models.TextField(blank=True)
    steps = models.TextField()
    safety_note = models.TextField(blank=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


# 9. Customer technical support tickets
class SupportTicket(models.Model):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In progress"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=180)
    description = models.TextField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="open"
    )
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default="normal"
    )
    staff_response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Ticket #{self.pk}: {self.subject}"
