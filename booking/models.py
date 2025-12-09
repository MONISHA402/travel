from django.db import models
from django.contrib.auth.models import User

class Destination(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    country = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to="destinations/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Package(models.Model):
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name="packages")
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    short_description = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField(default=1)
    total_slots = models.IntegerField(default=20)
    available_slots = models.IntegerField(default=20)
    start_date = models.DateField()
    end_date = models.DateField()
    cover_image = models.ImageField(upload_to="packages/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class PackageImage(models.Model):
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="packages/gallery/")


class Offer(models.Model):
    code = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=255, blank=True)
    discount_percent = models.IntegerField(default=0)
    active = models.BooleanField(default=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.code


class Booking(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("CONFIRMED", "Confirmed"),
        ("CANCELLED", "Cancelled"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="bookings")
    travelers = models.PositiveIntegerField(default=1)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    offer = models.ForeignKey(Offer, on_delete=models.SET_NULL, null=True, blank=True)
    booking_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    offer_code = models.CharField(max_length=50, blank=True, null=True)

    qr_code = models.CharField(max_length=255, null=True, blank=True)
    ticket_pdf = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"Booking #{self.id} - {self.user.username} - {self.package.title}"


class Payment(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="payment")
    razorpay_order_id = models.CharField(max_length=200, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=200, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payment for booking {self.booking.id} - Paid: {self.paid}"
