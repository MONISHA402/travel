from django.contrib import admin
from .models import Destination, Package, PackageImage, Offer, Booking, Payment

class PackageImageInline(admin.TabularInline):
    model = PackageImage
    extra = 1

@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ("title", "destination", "price", "start_date", "available_slots")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [PackageImageInline]

@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ("name", "country")
    prepopulated_fields = {"slug": ("name",)}

admin.site.register(Offer)
admin.site.register(Booking)
admin.site.register(Payment)
